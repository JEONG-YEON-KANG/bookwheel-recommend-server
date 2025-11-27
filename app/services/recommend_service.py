import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from app.models.model_loader import lightfm_model
from app.core.config import settings
from app.core.constants import (
    SURVEY_GENRE_MAPPING,
    SURVEY_MOOD_MAPPING,
    SURVEY_PURPOSE_MAPPING,
)


class RecommendService:
    def __init__(self):
        # 1. 모델 및 데이터 로드
        self.model = lightfm_model.model
        self.item_features = lightfm_model.item_features

        # 2. ID 매핑 로드
        self.item_map = lightfm_model.item_id_map  # DB ID -> 내부 ID
        self.rev_item_map = lightfm_model.rev_item_id_map  # 내부 ID -> DB ID
        self.user_map = lightfm_model.user_id_map
        self.rev_user_map = lightfm_model.rev_user_id_map

        # 3. DB 연결
        self.engine = create_engine(settings.DATABASE_URL)

        # 4. 아이템 벡터 미리 계산 (성능 최적화)
        self.all_item_vectors = self.item_features.dot(self.model.item_embeddings)

    # ------------------------------------------------------------------
    # [Helper] 결과 포맷팅 및 필터링 공통 함수
    # ------------------------------------------------------------------
    def _format_results(
        self, scores, k, exclude_indices=set(), id_map=None, key_name="book_idx"
    ):
        if id_map is None:
            id_map = self.rev_item_map

        ranked_indices = np.argsort(-scores)
        results = []
        for idx in ranked_indices:
            real_id = int(id_map[idx])
            if real_id in exclude_indices:
                continue
            results.append({key_name: real_id, "score": float(scores[idx])})
            if len(results) >= k:
                break
        return results

    # ------------------------------------------------------------------
    # [Helper] 옵션 Idx 리스트 -> 옵션 텍스트 리스트 변환
    # ------------------------------------------------------------------
    def _get_option_texts(self, option_idx_list: list[int]) -> list[str]:
        if not option_idx_list:
            return []
        ids_str = ",".join(map(str, option_idx_list))
        try:
            sql = f"SELECT content FROM survey_option_tb WHERE idx IN ({ids_str})"
            df = pd.read_sql(sql, self.engine)
            return df["content"].tolist()
        except Exception as e:
            print(f"Option Text SQL Error: {e}")
            return []

    # ------------------------------------------------------------------
    # 1. 책 -> 책 추천
    # ------------------------------------------------------------------
    def recommend_book_to_book(self, book_idx, k=10):
        if book_idx not in self.item_map:
            return []

        internal_idx = self.item_map[book_idx]
        target_vector = self.all_item_vectors[internal_idx]

        target_norm = np.linalg.norm(target_vector)
        all_norms = np.linalg.norm(self.all_item_vectors, axis=1)
        dot_products = self.all_item_vectors.dot(target_vector)
        scores = dot_products / (all_norms * target_norm + 1e-9)

        return self._format_results(
            scores=scores, k=k, exclude_indices={book_idx}, key_name="book_idx"
        )

    # ------------------------------------------------------------------
    # 2. 유저 -> 책 추천
    # ------------------------------------------------------------------
    def recommend_books_for_user(self, user_idx, k=10):
        if user_idx not in self.user_map:
            return []

        internal_user = self.user_map[user_idx]
        read_book_set = set()
        try:
            read_books_df = pd.read_sql(
                f"SELECT book_idx FROM book_rating_tb WHERE user_idx = {user_idx} AND deleted_at IS NULL",
                self.engine,
            )
            read_book_set = set(read_books_df["book_idx"].tolist())
        except Exception as e:
            print(f"History Query Error: {e}")

        n_items = self.item_features.shape[0]
        scores = self.model.predict(
            user_ids=internal_user,
            item_ids=np.arange(n_items),
            item_features=self.item_features,
        )

        return self._format_results(
            scores=scores, k=k, exclude_indices=read_book_set, key_name="book_idx"
        )

    # ------------------------------------------------------------------
    # 3. 태그 (+책) -> 책 추천 (문자열 태그 기반)
    # ------------------------------------------------------------------
    def recommend_tag_book(self, book_idx=None, tag_list=[], k=10):
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

        book_vec = np.zeros(self.model.item_embeddings.shape[1])
        exclude_set = set()

        if book_idx is not None and book_idx in self.item_map:
            book_vec = self.all_item_vectors[self.item_map[book_idx]]
            hybrid_vec = 0.5 * tag_vec + 0.5 * book_vec
            exclude_set.add(book_idx)
        else:
            hybrid_vec = tag_vec

        if np.all(hybrid_vec == 0):
            return []

        scores = self.all_item_vectors.dot(hybrid_vec)
        return self._format_results(
            scores=scores, k=k, exclude_indices=exclude_set, key_name="book_idx"
        )

    # ------------------------------------------------------------------
    # 4. 유저 -> 유저 추천
    # ------------------------------------------------------------------
    def recommend_user_to_user(self, user_idx, k=10):
        if user_idx not in self.user_map:
            return []

        internal_user = self.user_map[user_idx]
        u_vecs = self.model.user_embeddings
        target_vec = u_vecs[internal_user]

        u_norms = np.linalg.norm(u_vecs, axis=1)
        target_norm = np.linalg.norm(target_vec)

        dot_products = u_vecs.dot(target_vec)
        scores = dot_products / (u_norms * target_norm + 1e-9)

        return self._format_results(
            scores=scores,
            k=k,
            exclude_indices={user_idx},
            id_map=self.rev_user_map,
            key_name="user_idx",
        )

    # ------------------------------------------------------------------
    # 5. [NEW] 설문 기반 초기 추천 (ID 기반 - Cold Start)
    # ------------------------------------------------------------------
    def get_initial_recommendation(
        self,
        genre_id_list: list[int],
        mood_id_list: list[int],
        purpose_id_list: list[int],
        book_id_list: list[int],
        k=10,
    ):
        """
        설문조사 ID 리스트를 받아 텍스트로 변환 후 추천 로직 수행
        """
        # 1. ID -> 텍스트 변환
        genre_list = self._get_option_texts(genre_id_list)
        mood_list = self._get_option_texts(mood_id_list)
        purpose_list = self._get_option_texts(purpose_id_list)

        # 2. 텍스트 -> 검색할 실제 태그 이름 수집 (매핑 활용)
        target_tag_names = set()

        for g in genre_list:
            if g in SURVEY_GENRE_MAPPING:
                target_tag_names.update(SURVEY_GENRE_MAPPING[g])
        for m in mood_list:
            if m in SURVEY_MOOD_MAPPING:
                target_tag_names.update(SURVEY_MOOD_MAPPING[m])
        for p in purpose_list:
            if p in SURVEY_PURPOSE_MAPPING:
                target_tag_names.update(SURVEY_PURPOSE_MAPPING[p])

        target_tag_names = list(target_tag_names)

        # 3. 태그 벡터 계산
        tag_vec = np.zeros(self.model.item_embeddings.shape[1])
        if target_tag_names:
            escaped_tags = [t.replace("'", "''") for t in target_tag_names]
            quoted_tags = ",".join(f"'{t.lower()}'" for t in escaped_tags)

            try:
                sql = f"""
                    SELECT DISTINCT bt.book_idx 
                    FROM tag_tb t 
                    JOIN book_tag_tb bt ON t.idx = bt.tag_idx 
                    WHERE LOWER(t.name) IN ({quoted_tags})
                """
                df = pd.read_sql(sql, self.engine)
                valid_indices = [
                    self.item_map[b] for b in df["book_idx"] if b in self.item_map
                ]
                if valid_indices:
                    tag_vec = self.all_item_vectors[valid_indices].mean(axis=0)
            except Exception as e:
                print(f"Init Tag SQL Error: {e}")

        # 4. 책 벡터 계산
        book_vec = np.zeros(self.model.item_embeddings.shape[1])
        exclude_books = set()

        if book_id_list:
            valid_book_indices = []
            for bid in book_id_list:
                if bid in self.item_map:
                    valid_book_indices.append(self.item_map[bid])
                    exclude_books.add(bid)

            if valid_book_indices:
                book_vec = self.all_item_vectors[valid_book_indices].mean(axis=0)

        # 5. 벡터 합성
        if np.all(tag_vec == 0) and np.all(book_vec == 0):
            return []

        if np.all(tag_vec == 0):
            hybrid_vec = book_vec
        elif np.all(book_vec == 0):
            hybrid_vec = tag_vec
        else:
            hybrid_vec = 0.5 * tag_vec + 0.5 * book_vec

        # 6. 결과 반환
        scores = self.all_item_vectors.dot(hybrid_vec)
        return self._format_results(
            scores=scores, k=k, exclude_indices=exclude_books, key_name="book_idx"
        )
