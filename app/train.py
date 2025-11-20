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
# 텍스트 분석 라이브러리
from sklearn.feature_extraction.text import TfidfVectorizer

def run_training():
    load_dotenv()
    ARTIFACTS_DIR = "app/artifacts"
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    engine = create_engine(os.getenv("DATABASE_URL"))
    print("--- [1/6] 데이터 로딩 ---")

    # 1. 데이터 로드 (Author, Description 포함)
    ratings = pd.read_sql("SELECT user_idx, book_idx, rating FROM book_rating_tb WHERE deleted_at IS NULL", engine)
    books = pd.read_sql("SELECT idx AS book_idx, author, description FROM book_tb WHERE deleted_at IS NULL", engine)
    tags = pd.read_sql("SELECT idx AS tag_idx, name FROM tag_tb", engine)
    book_tags = pd.read_sql("SELECT book_idx, tag_idx FROM book_tag_tb", engine)

    # 2. 평점 전처리 (Implicit >= 4)
    ratings = ratings.groupby(["user_idx", "book_idx"])["rating"].mean().reset_index()
    ratings = ratings[ratings["rating"] >= 4]
    ratings["rating"] = 1.0

    # 3. 태그 전처리 (최소 5회 이상 등장 태그만)
    bt = book_tags.merge(tags, on="tag_idx")
    tag_counts = bt['name'].value_counts()
    valid_tags = tag_counts[tag_counts >= 5].index
    bt = bt[bt['name'].isin(valid_tags)]
    book_tags_map = bt.groupby("book_idx")["name"].apply(list).to_dict()
    
    # 4. Description 전처리 (TF-IDF)
    print("--- [2/6] 줄거리(Description) 키워드 추출 중... ---")
    books["description"] = books["description"].fillna("")
    # 중요: 줄거리에서 가장 핵심적인 단어 300개만 뽑음 (너무 많으면 노이즈)
    tfidf = TfidfVectorizer(max_features=300, stop_words='english')
    tfidf_matrix = tfidf.fit_transform(books["description"])
    vocab = tfidf.get_feature_names_out() # 추출된 단어들 (예: magic, war, love...)

    # 5. Feature 리스트 생성 (Author + Tag + Desc)
    print("--- [3/6] 모든 Feature 합체 중... ---")
    feature_list = []
    
    # 인덱싱 속도 최적화를 위해 list 변환
    book_ids = books['book_idx'].values
    authors = books['author'].values
    
    for i, book_id in enumerate(book_ids):
        feats = []
        
        # A. 작가 (Author)
        if authors[i]:
            feats.append(f"author:{authors[i]}")
        
        # B. 태그 (Tag)
        if book_id in book_tags_map:
            feats.extend([f"tag:{t}" for t in book_tags_map[book_id]])
            
        # C. 줄거리 키워드 (Description)
        # tfidf_matrix는 희소 행렬이므로 해당 책의 단어 인덱스만 가져옴
        word_indices = tfidf_matrix[i].indices
        for idx in word_indices:
            feats.append(f"desc:{vocab[idx]}")
            
        feature_list.append((book_id, feats))

    # 6. Dataset 빌드
    dataset = Dataset()
    
    all_features = set()
    for _, feats in feature_list:
        all_features.update(feats)

    dataset.fit(
        users=ratings["user_idx"].unique(),
        items=books["book_idx"].unique(),
        item_features=all_features
    )

    interactions, _ = dataset.build_interactions(
        (u, i) for u, i in ratings[["user_idx", "book_idx"]].itertuples(index=False)
    )

    item_features = dataset.build_item_features(feature_list)

    # 7. Train / Test 분리
    train, test = random_train_test_split(interactions, test_percentage=0.2, random_state=42)

    # 8. 학습
    print("--- [4/6] 모델 학습 시작 ---")
    model = LightFM(
        loss="warp",
        no_components=40,
        learning_rate=0.05,
        item_alpha=0.0001, # Feature가 많아졌으므로 약한 규제 적용
        random_state=42
    )
    model.fit(train, item_features=item_features, epochs=20, num_threads=1, verbose=True)

    # 9. 평가
    print("--- [5/6] 평가 진행 ---")
    k = 10
    test_precision = precision_at_k(model, test, item_features=item_features, k=k, num_threads=1).mean()
    test_auc = auc_score(model, test, item_features=item_features, num_threads=1).mean()

    print(f"✅ Test Precision@{k}: {test_precision:.4f}")
    print(f"✅ Test AUC:            {test_auc:.4f}")

    # 10. 저장
    print("--- [6/6] 저장 ---")
    with open(f"{ARTIFACTS_DIR}/lightfm_model.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(f"{ARTIFACTS_DIR}/lightfm_dataset.pkl", "wb") as f:
        pickle.dump(dataset, f)
    with open(f"{ARTIFACTS_DIR}/item_features.pkl", "wb") as f:
        pickle.dump(item_features, f)
    
    bt.to_pickle(f"{ARTIFACTS_DIR}/book_tags_df.pkl")
    
    print("🎉 모든 학습 과정 완료! (Author + Tag + Description)")

if __name__ == "__main__":
    run_training()