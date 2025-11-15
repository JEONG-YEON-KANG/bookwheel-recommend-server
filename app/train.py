import os
import pickle
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv

from lightfm import LightFM
from lightfm.data import Dataset
from lightfm.evaluation import precision_at_k, recall_at_k, auc_score
from lightfm.cross_validation import random_train_test_split

def run_training():
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL is None:
        raise ValueError("DATABASE_URL is not set in environment variables.")

    engine = create_engine(DATABASE_URL)

    ratings = pd.read_sql("""
        SELECT user_idx, book_idx, rating
        FROM book_rating_tb
        WHERE deleted_at IS NULL
    """, engine)

    books = pd.read_sql("""
        SELECT idx as book_idx, author, publication_year
        FROM book_tb
        WHERE deleted_at IS NULL
    """, engine)

    tags = pd.read_sql("""
        SELECT idx AS tag_idx, name
        FROM tag_tb
    """, engine)

    book_tags = pd.read_sql("""
        SELECT book_idx, tag_idx
        FROM book_tag_tb
    """, engine)

    # 3. 전처리 
    year = pd.to_numeric(books['publication_year'], errors='coerce').fillna(0).astype(int)
    decade = np.where(year > 0, (year // 10) * 10, -1)
    books["decade"] = np.where(decade >= 0, (decade.astype(str) + "s"), "unknown")

    ratings = ratings.groupby(["user_idx", "book_idx"])["rating"].mean().reset_index()

    ratings["rating"] = (ratings["rating"] > 4).astype(np.float32)

    valid_books = ratings["book_idx"].value_counts()[lambda x: x >= 3].index
    ratings = ratings[ratings["book_idx"].isin(valid_books)]

    bt = book_tags.merge(tags, on="tag_idx", how="left")

    usage = bt.groupby("tag_idx")["book_idx"].count().reset_index().rename(columns={"book_idx":"usage_count"})
    bt = bt.merge(usage, on="tag_idx", how="left")

    TAG_MIN = 3
    TAG_MAX = 606
    bt = bt[(bt["usage_count"] >= TAG_MIN) & (bt["usage_count"] <= TAG_MAX)]

    bt = bt.sort_values(["book_idx", "usage_count"], ascending=[True, False])

    TOP_K = 20
    bt_top = bt.groupby("book_idx").head(TOP_K)

    book_tags_map = (
        bt_top.groupby("book_idx")["name"].apply(list).to_dict()
    )

    # 4. 피처 생성 함수
    def build_item_features(row) :
        feats = []
        feats.append(f"author:{row['author']}")
        feats.append(f"decade:{row['decade']}")
        for t in book_tags_map.get(row["book_idx"], []):
            feats.append(f"tag:{t}")
        return feats

    books["features"] = books.apply(build_item_features, axis=1)

    dataset = Dataset()

    all_item_features = set()
    for feats in books["features"]:
        all_item_features.update(feats)
        
    dataset.fit(
        users=ratings["user_idx"].unique(),
        items=ratings["book_idx"].unique(),
        item_features=all_item_features
    )

    (interactions, _) = dataset.build_interactions(
        (u,i,r) for u, i, r in ratings[["user_idx", "book_idx", "rating"]].itertuples(index=False)
    )

    item_features = dataset.build_item_features(
        ((row["book_idx"], row["features"]) for _, row in books.iterrows())
    )

    train, test = random_train_test_split(interactions, test_percentage=0.1, random_state=42)

    model = LightFM(loss="warp", no_components=64, learning_rate=0.05, random_state=42)
    model.fit(train, item_features=item_features, epochs=10, num_threads=4, verbose=True)

    k = 10
    precision = precision_at_k(model, test, item_features=item_features, k=k).mean()
    recall = recall_at_k(model, test, item_features=item_features, k=k).mean()
    auc = auc_score(model, test, item_features=item_features).mean()

    print(f"Precision@{k}: {precision:.4f}")
    print(f"Recall@{k}:    {recall:.4f}")
    print(f"AUC:           {auc:.4f}")

    # 모델 및 데이터셋 저장
    save_path = "models"
    if not os.path.exists(save_path):
        os.makedirs(save_path)
        
    with open(os.path.join(save_path, "lightfm_model.pkl"), "wb") as f:
        pickle.dump(model, f)

    with open(os.path.join(save_path, "lightfm_dataset.pkl"), "wb") as f:
        pickle.dump(dataset, f)
        
    with open(os.path.join(save_path, "item_features.pkl"), "wb") as f:
        pickle.dump(item_features, f)
        
if __name__ == "__main__":
    try:
        run_training()
    except Exception as e:
        print(f"❌ 학습 중 오류 발생: {e}")

