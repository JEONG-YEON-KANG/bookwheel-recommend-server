import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from app.models.model_loader import lightfm_model
from app.core.config import settings


class RecommenderService:
    def __init__(self):
        # 1. 모델 및 데이터 로드
        self.model = lightfm_model.model
        self.item_features = lightfm_model.item_features

        # 2. ID 매핑 로드
        self.item_map = lightfm_model.item_id_map       # DB ID -> 내부 ID
        self.rev_item_map = lightfm_model.rev_item_id_map  # 내부 ID -> DB ID
        self.user_map = lightfm_model.user_id_map
        self.rev_user_map = lightfm_model.rev_user_id_map

        # 3. DB 연결
        self.engine = create_engine(settings.DATABASE_URL)

        # 4. 아이템 벡터 미리 계산
        self.all_item_vectors = self.item_features.dot(
            self.model.item_embeddings)

    # ------------------------------------------------------------------
    # 결과 포맷팅 및 필터링 공통 함수
    # ------------------------------------------------------------------
    def _format_results(self, scores, k, exclude_indices=set(), id_map=None, key_name="book_idx"):
        """
        점수 배열을 받아 정렬 후, 제외할 인덱스를 빼고 최종 리스트를 반환
        """
        if id_map is None:
            id_map = self.rev_item_map

        # 점수 내림차순 정렬
        ranked_indices = np.argsort(-scores)

        results = []
        for idx in ranked_indices:
            real_id = int(id_map[idx])

            # 제외할 ID 건너뛰기
            if real_id in exclude_indices:
                continue

            results.append({
                key_name: real_id,
                "score": float(scores[idx])
            })

            if len(results) >= k:
                break

        return results

    # ------------------------------------------------------------------
    # 1. 책 -> 책 추천
    # ------------------------------------------------------------------
    def recommend_book_to_book(self, book_idx, k=10):
        if book_idx not in self.item_map:
            return []

        internal_idx = self.item_map[book_idx]
        target_vector = self.all_item_vectors[internal_idx]

        # 코사인 유사도 계산
        target_norm = np.linalg.norm(target_vector)
        all_norms = np.linalg.norm(self.all_item_vectors, axis=1)
        dot_products = self.all_item_vectors.dot(target_vector)

        # 0 나누기 방지
        scores = dot_products / (all_norms * target_norm + 1e-9)

        # 공통 함수로 결과 반환 (자기 자신 제외)
        return self._format_results(
            scores=scores,
            k=k,
            exclude_indices={book_idx},
            key_name="book_idx"
        )

    # ------------------------------------------------------------------
    # 2. 유저 -> 책 추천
    # ------------------------------------------------------------------
    def recommend_books_for_user(self, user_idx, k=10):
        if user_idx not in self.user_map:
            return []

        internal_user = self.user_map[user_idx]

        # 이미 읽은 책 목록 가져오기
        read_book_set = set()
        try:
            read_books_df = pd.read_sql(
                f"SELECT book_idx FROM book_rating_tb WHERE user_idx = {user_idx} AND deleted_at IS NULL",
                self.engine
            )
            read_book_set = set(read_books_df["book_idx"].tolist())
        except Exception as e:
            print(f"History Query Error: {e}")

        # 모델 예측
        n_items = self.item_features.shape[0]
        scores = self.model.predict(
            user_ids=internal_user,
            item_ids=np.arange(n_items),
            item_features=self.item_features
        )

        # 공통 함수로 결과 반환
        return self._format_results(
            scores=scores,
            k=k,
            exclude_indices=read_book_set,
            key_name="book_idx"
        )

    # ------------------------------------------------------------------
    # 3. 태그 (+책) -> 책 추천
    # ------------------------------------------------------------------
    def recommend_tag_book(self, book_idx=None, tag_list=[], k=10):
        # 1. 태그 벡터 계산
        tag_vec = np.zeros(self.model.item_embeddings.shape[1])

        if tag_list:
            lower_tags = [str(t).lower() for t in tag_list]
            escaped_tags = [t.replace("'", "''") for t in lower_tags]
            quoted_tags = ",".join(f"'{t}'" for t in escaped_tags)

            sql = f"""
                SELECT DISTINCT bt.book_idx
                FROM tag_tb t
                JOIN book_tag_tb bt ON t.idx = bt.tag_idx
                WHERE LOWER(t.name) IN ({quoted_tags})
            """
            try:
                df = pd.read_sql(sql, self.engine)
                valid_indices = [
                    self.item_map[b] for b in df["book_idx"] if b in self.item_map
                ]
                if valid_indices:
                    tag_vec = self.all_item_vectors[valid_indices].mean(axis=0)
            except Exception as e:
                print(f"Tag SQL Error: {e}")

        # 2. 하이브리드 벡터 계산
        hybrid_vec = tag_vec
        exclude_set = set()

        if book_idx is not None and book_idx in self.item_map:
            book_vec = self.all_item_vectors[self.item_map[book_idx]]
            hybrid_vec = 0.5 * tag_vec + 0.5 * book_vec
            exclude_set.add(book_idx)  # 기준 책은 결과에서 제외

        # 검색된 태그도 없고 책도 없는 경우
        if np.all(hybrid_vec == 0):
            return []

        # 3. 유사도 검색
        scores = self.all_item_vectors.dot(hybrid_vec)

        # 공통 함수로 결과 반환
        return self._format_results(
            scores=scores,
            k=k,
            exclude_indices=exclude_set,
            key_name="book_idx"
        )

    # ------------------------------------------------------------------
    # 4. 유저 -> 유저 추천
    # ------------------------------------------------------------------
    def recommend_user_to_user(self, user_idx, k=10):
        if user_idx not in self.user_map:
            return []

        internal_user = self.user_map[user_idx]

        # 유저 벡터 가져오기
        u_vecs = self.model.user_embeddings
        target_vec = u_vecs[internal_user]

        # 코사인 유사도 계산
        u_norms = np.linalg.norm(u_vecs, axis=1)
        target_norm = np.linalg.norm(target_vec)

        dot_products = u_vecs.dot(target_vec)
        scores = dot_products / (u_norms * target_norm + 1e-9)

        # 공통 함수로 결과 반환
        return self._format_results(
            scores=scores,
            k=k,
            exclude_indices={user_idx},
            id_map=self.rev_user_map,
            key_name="user_idx"
        )
