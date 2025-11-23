import os
import pickle
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv

from lightfm import LightFM
from lightfm.data import Dataset
from lightfm.cross_validation import random_train_test_split
from lightfm.evaluation import precision_at_k, auc_score


def run_training():

    load_dotenv()
    ARTIFACTS_DIR = "app/artifacts"
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    engine = create_engine(os.getenv("DATABASE_URL"))

    print("\n=== [1/5] 데이터 로딩 ===")

    # ----------------------------------------------------
    # 1. 데이터 로드
    # ----------------------------------------------------
    ratings = pd.read_sql("""
        SELECT user_idx, book_idx, rating
        FROM book_rating_tb
        WHERE deleted_at IS NULL
    """, engine)

    books = pd.read_sql("""
        SELECT idx AS book_idx, author
        FROM book_tb
        WHERE deleted_at IS NULL
    """, engine)

    tags = pd.read_sql("SELECT idx AS tag_idx, name FROM tag_tb", engine)
    book_tags = pd.read_sql(
        "SELECT book_idx, tag_idx FROM book_tag_tb", engine)

    # ----------------------------------------------------
    # 2. 평점 전처리 (implicit)
    # ----------------------------------------------------
    ratings = ratings.groupby(["user_idx", "book_idx"])[
        "rating"].mean().reset_index()
    ratings = ratings[ratings["rating"] >= 4]
    ratings["rating"] = 1.0   # implicit

    # ----------------------------------------------------
    # 3. 태그 전처리 (필터링 없이 모든 태그 유지)
    # ----------------------------------------------------
    bt = book_tags.merge(tags, on="tag_idx", how="left")
    book_tags_map = bt.groupby("book_idx")["name"].apply(list).to_dict()

    # ----------------------------------------------------
    # 4. Feature 리스트 만들기 (Author + Tag)
    # ----------------------------------------------------
    print("=== [2/5] Feature 생성 중 ===")

    feature_list = []
    for _, row in books.iterrows():

        book_id = row["book_idx"]
        feats = []

        # author feature
        if pd.notna(row["author"]):
            feats.append(f"author:{row['author']}")

        # tag feature
        if book_id in book_tags_map:
            feats.extend([f"tag:{t}" for t in book_tags_map[book_id]])

        # feature 없는 책도 반드시 포함해야 함!
        feature_list.append((book_id, feats))

    # ----------------------------------------------------
    # 5. Dataset 구성 (책 전체 포함!)
    # ----------------------------------------------------
    print("=== [3/5] Dataset 구성 중 ===")

    dataset = Dataset()

    all_features = {feat for _, feats in feature_list for feat in feats}

    dataset.fit(
        users=ratings["user_idx"].unique(),
        items=books["book_idx"].unique(),   # ★ 책 전체 포함
        item_features=all_features
    )

    interactions, _ = dataset.build_interactions(
        (u, i) for u, i in ratings[["user_idx", "book_idx"]].itertuples(index=False)
    )

    item_features = dataset.build_item_features(feature_list)

    # ----------------------------------------------------
    # 6. Train/Test split
    # ----------------------------------------------------
    train, test = random_train_test_split(
        interactions, test_percentage=0.2, random_state=42
    )

    # ----------------------------------------------------
    # 7. LightFM 학습
    # ----------------------------------------------------
    print("=== [4/5] LightFM 학습 시작 ===")

    model = LightFM(
        loss="warp",
        no_components=40,
        learning_rate=0.05,
        random_state=42
    )

    model.fit(
        train,
        item_features=item_features,
        epochs=20,
        num_threads=4,
        verbose=True
    )

    # ----------------------------------------------------
    # 8. 평가
    # ----------------------------------------------------
    print("=== [5/5] 평가 ===")

    k = 10
    precision = precision_at_k(
        model, test, item_features=item_features, k=k).mean()
    auc = auc_score(model, test, item_features=item_features).mean()

    print(f"\nPrecision@10: {precision:.4f}")
    print(f"AUC:          {auc:.4f}\n")

    # ----------------------------------------------------
    # 9. 저장
    # ----------------------------------------------------
    with open(f"{ARTIFACTS_DIR}/lightfm_model.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(f"{ARTIFACTS_DIR}/lightfm_dataset.pkl", "wb") as f:
        pickle.dump(dataset, f)
    with open(f"{ARTIFACTS_DIR}/item_features.pkl", "wb") as f:
        pickle.dump(item_features, f)

    print("모든 학습 완료")


if __name__ == "__main__":
    run_training()
