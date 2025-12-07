import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from app.models.model_loader import lightfm_model
from app.core.config import settings
from app.core.constants import (
    SURVEY_GENRE_MAPPING,
    SURVEY_MOOD_MAPPING,
    SURVEY_PURPOSE_MAPPING,
    GENRE_SECTION_ORDER,
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

    # -----------------------------------------------------------------
    # [Helper] 결과 포맷팅 및 필터링 공통 함수
    # 점수 벡터 -> 상위 k개 추출 + exclude 적용 + 내부 중복 제거
    # exclude_indices: nestjs가 전달한 제외 대상
    # -----------------------------------------------------------------
    def _format_results(
        self, scores, k, exclude_indices=set(), idx_map=None, key_name="book_idx"
    ):
        if idx_map is None:
            idx_map = self.rev_item_map

        ranked = np.argsort(-scores)  # 높은 점수 순으로 정렬
        results = []
        used_idx_list = set()  # 내부 중복 제거

        for internal_idx in ranked:
            real_idx = int(idx_map[internal_idx])

            # 섹션 간 중복 제거
            if real_idx in exclude_indices:
                continue

            # 내부 중복 제거
            if real_idx in used_idx_list:
                continue

            # 결과 추가
            results.append({key_name: real_idx})

            used_idx_list.add(real_idx)
            exclude_indices.add(real_idx)

            if len(results) >= k:
                break

        return results

    # -----------------------------------------------------------------
    # [Helper] 옵션 Idx 리스트 -> 옵션 텍스트 리스트 변환 (설문조사)
    # 옵션 idx를 DB에서 조회하여 텍스트로 변환
    # -----------------------------------------------------------------
    def _get_option_texts(self, option_idx_list: list[int]) -> list[str]:
        if not option_idx_list:
            return []

        placeholders = ", ".join([f":id_{i}" for i in range(len(option_idx_list))])
        params = {f"id_{i}": idx for i, idx in enumerate(option_idx_list)}

        sql = text(
            f"SELECT content FROM survey_option_tb WHERE idx IN ({placeholders})"
        )

        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(sql, conn, params=params)

            return df["content"].tolist()
        except Exception as e:
            print(f"Option Text SQL Error: {e}")
            return []

    # -----------------------------------------------------------------
    # [Helper] 태그 이름 리스트 -> 벡터로 변환
    # -----------------------------------------------------------------
    def _get_tag_vector(self, tag_name_list: list[str]) -> np.ndarray:
        if not tag_name_list:
            return np.zeros(self.model.item_embeddings.shape[1])

        lower_tag_list = [str(t).lower() for t in tag_name_list if t]

        placeholders = ", ".join([f":tag_{i}" for i in range(len(lower_tag_list))])
        params = {f"tag_{i}": tag for i, tag in enumerate(lower_tag_list)}
        sql = text(
            f"""
            SELECT DISTINCT bt.book_idx
            FROM tag_tb t JOIN book_tag_tb bt ON t.idx = bt.tag_idx
            WHERE LOWER(t.name) IN ({placeholders})
        """
        )
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(sql, conn, params=params)

            valid_indices = [
                self.item_map[bidx]
                for bidx in df["book_idx"].tolist()
                if bidx in self.item_map
            ]
            if valid_indices:
                return self.all_item_vectors[valid_indices].mean(axis=0)
        except Exception as e:
            print(f"Tag Vector SQL Error: {e}")
        return np.zeros(self.model.item_embeddings.shape[1])

    # -----------------------------------------------------------------
    # [Helper] 코사인 유사도 기반 추천 점수 계산
    # -----------------------------------------------------------------
    def _compute_cosine_scores(self, target_vec: np.ndarray) -> np.ndarray:
        if np.all((target_vec == 0)):
            return np.zeros(self.all_item_vectors.shape[0])

        item_norms = np.linalg.norm(self.all_item_vectors, axis=1)
        target_norm = np.linalg.norm(target_vec)

        denominator = item_norms * target_norm
        denominator[denominator == 0] = 1e-9

        scores = (self.all_item_vectors.dot(target_vec)) / denominator
        return scores

    # -----------------------------------------------------------------
    # [Helper] cold 여부 + recent 추천 가능 여부 판단
    # warm_user : rating_count >= 3
    # recent_available : read_count >= 1
    # -----------------------------------------------------------------
    def _get_user_status(self, user_idx: int):
        rating_count, read_count = 0, 0
        progress_threshold = 0.2

        rating_sql = text(
            "SELECT COUNT(*) AS cnt FROM book_rating_tb WHERE user_idx = :user_idx AND deleted_at IS NULL"
        )
        progress_my_sql = text(
            "SELECT COUNT(*) AS cnt FROM my_book_progress_tb WHERE user_idx = :user_idx AND progress >= :threshold"
        )
        progress_party_sql = text(
            "SELECT COUNT(*) AS cnt FROM party_book_progress_tb WHERE user_idx = :user_idx AND progress >= :threshold"
        )

        params = {"user_idx": user_idx, "threshold": progress_threshold}

        # -------------------------
        # 1) rating count
        # -------------------------
        try:
            df_rating = pd.read_sql(
                rating_sql, self.engine, params={"user_idx": user_idx}
            )

            rating_count = int(df_rating["cnt"].iloc[0]) if not df_rating.empty else 0
        except Exception as e:
            print(f"Rating Count Query Error: {e}")

        warm = rating_count >= 3

        # -------------------------
        # 2) 읽은 책 count (progress)
        # my_book_progress_tb + party_book_progress_tb 통합
        # progress >= 0.2 이상만 인정
        # -------------------------
        try:
            df1 = pd.read_sql(progress_my_sql, self.engine, params=params)
            read_count = int(df1["cnt"].iloc[0]) if not df1.empty else 0
        except Exception as e:
            print(f"My Book Progress Query Error: {e}")

        try:
            df2 = pd.read_sql(progress_party_sql, self.engine, params=params)
            read_count += int(df2["cnt"].iloc[0]) if not df2.empty else 0
        except Exception as e:
            print(f"Party Book Progress Query Error: {e}")

        recent_available = read_count >= 1
        return warm, recent_available

    # -----------------------------------------------------------------
    # [Helper] 설문 응답 로드
    # -----------------------------------------------------------------
    def _load_survey_response(self, user_idx: int):
        sql = text(
            """
            SELECT 
                Q.idx AS question_idx,
                O.idx AS option_idx,
                O.book_idx AS book_idx
            FROM survey_response_tb R
            JOIN survey_option_tb O ON R.option_idx = O.idx
            JOIN survey_question_tb Q ON O.question_idx = Q.idx
            WHERE R.user_idx = :user_idx
        """
        )

        df = pd.read_sql(sql, self.engine, params={"user_idx": user_idx})

        genre_list = []
        mood_list = []
        purpose_list = []
        book_idx_list = []

        for _, row in df.iterrows():
            qid = int(row["question_idx"])
            opt = int(row["option_idx"])
            bidx = row["book_idx"]

            if qid == 1:
                genre_list.append(opt)
            elif qid == 2:
                mood_list.append(opt)
            elif qid == 3:
                purpose_list.append(opt)
            elif qid == 4:
                if bidx:
                    book_idx_list.append(int(bidx))

        return genre_list, mood_list, purpose_list, book_idx_list

    # -----------------------------------------------------------------
    # 유저 -> 유저 추천
    # -----------------------------------------------------------------
    def recommend_similar_user(self, user_idx: int, k: int = 10):
        if user_idx not in self.user_map:
            return []

        internal_user = self.user_map[user_idx]
        u_vecs = self.model.user_embeddings
        target_vec = u_vecs[internal_user]

        if np.all((target_vec == 0)):
            return []

        u_norms = np.linalg.norm(u_vecs, axis=1)
        target_norm = np.linalg.norm(target_vec)

        dot_products = u_vecs.dot(target_vec)
        denominator = u_norms * target_norm
        denominator[denominator == 0] = 1e-9

        scores = dot_products / denominator

        return self._format_results(
            scores,
            k,
            exclude_indices={user_idx},
            idx_map=self.rev_user_map,
            key_name="user_idx",
        )

    # -----------------------------------------------------------------
    # 개인화 추천 top1
    # -----------------------------------------------------------------
    def _recommend_personal_top1(self, user_idx: int):
        if user_idx not in self.user_map:
            return None

        top_list = self._recommend_personal(user_idx, k=1)
        return top_list[0] if top_list else None

    # -----------------------------------------------------------------
    # 개인화 추천 top10
    # -----------------------------------------------------------------
    def _recommend_personal(
        self,
        user_idx: int,
        k: int = 10,
        exclude_indices: list[int] = [],
    ):
        if user_idx not in self.user_map:
            return []

        internal_user = self.user_map[user_idx]
        exclude_set = set(exclude_indices)

        sql = text(
            "SELECT book_idx FROM book_rating_tb WHERE user_idx = :user_idx AND deleted_at IS NULL"
        )

        try:
            read_books_df = pd.read_sql(sql, self.engine, params={"user_idx": user_idx})
            exclude_set.update(read_books_df["book_idx"].tolist())
        except Exception as e:
            print(f"History Query Error: {e}")

        n_items = self.item_features.shape[0]
        scores = self.model.predict(
            user_ids=internal_user,
            item_ids=np.arange(n_items),
            item_features=self.item_features,
        )

        return self._format_results(scores, k, exclude_indices=exclude_set)

    # -----------------------------------------------------------------
    # 유사 도서 추천
    # -----------------------------------------------------------------
    def recommend_similar_book(
        self, book_idx: int, k: int = 10, exclude_indices: list[int] = None
    ):
        if book_idx not in self.item_map:
            return []

        internal_idx = self.item_map[book_idx]
        target_vector = self.all_item_vectors[internal_idx]

        if exclude_indices is None:
            exclude_set = {book_idx}
        else:
            exclude_set = set(exclude_indices)
            exclude_set.add(book_idx)

        scores = self._compute_cosine_scores(target_vector)

        return self._format_results(scores, k, exclude_indices=exclude_set)

    # -----------------------------------------------------------------
    # 최근 읽은 책 기반 추천
    # -----------------------------------------------------------------
    def _recommend_recent(
        self, user_idx: int, k: int = 10, exclude_indices: list[int] = []
    ):
        exclude_set = set(exclude_indices)

        progress_threshold = 0.2

        sql = text(
            """
            SELECT book_idx, updated_at
            FROM (
                SELECT book_idx, updated_at
                FROM my_book_progress_tb
                WHERE user_idx = :user_idx AND progress >= :threshold

                UNION ALL

                SELECT p.book_idx as book_idx,
                pbp.updated_at
                FROM party_book_progress_tb AS pbp
                JOIN party_tb AS p
                    ON pbp.party_idx = p.idx
                WHERE pbp.user_idx = :user_idx AND pbp.progress >= :threshold
            ) AS combined
            ORDER BY updated_at DESC
            LIMIT 1
        """
        )

        params = {"user_idx": user_idx, "threshold": progress_threshold}

        try:
            df = pd.read_sql(sql, self.engine, params=params)
            if df.empty or "book_idx" not in df or pd.isna(df["book_idx"].iloc[0]):
                return []

            recent_book_idx = int(df["book_idx"].iloc[0])

            exclude_set.add(recent_book_idx)

            return self.recommend_similar_book(
                recent_book_idx, k, exclude_indices=exclude_set
            )
        except Exception as e:
            print(f"Recent Book Query Error: {e}")
            return []

    # -----------------------------------------------------------------
    # 설문 기반 top1 추천
    # -----------------------------------------------------------------
    def _recommend_initial_top1(
        self,
        genre_list: list[int],
        mood_list: list[int],
        purpose_list: list[int],
        book_idx_list: list[int],
    ):
        result = self._recommend_initial(
            genre_list, mood_list, purpose_list, book_idx_list, k=1, exclude_indices=[]
        )
        return result[0] if result else None

    # -----------------------------------------------------------------
    # 설문 기반 top10 추천
    # -----------------------------------------------------------------
    def _recommend_initial(
        self,
        genre_list: list[int],
        mood_list: list[int],
        purpose_list: list[int],
        book_idx_list: list[int],
        k: int = 10,
        exclude_indices: list[int] = [],
    ):
        exclude_set = set(exclude_indices)

        # 1. Idx -> 텍스트 변환
        genre_list = self._get_option_texts(genre_list)
        mood_list = self._get_option_texts(mood_list)
        purpose_list = self._get_option_texts(purpose_list)

        # 2. 텍스트 -> 검색할 실제 태그 이름 수집 (매핑 활용)
        tag_name_list = set()

        for g in genre_list:
            if g in SURVEY_GENRE_MAPPING:
                tag_name_list.update(SURVEY_GENRE_MAPPING.get(g, []))
        for m in mood_list:
            if m in SURVEY_MOOD_MAPPING:
                tag_name_list.update(SURVEY_MOOD_MAPPING.get(m, []))
        for p in purpose_list:
            if p in SURVEY_PURPOSE_MAPPING:
                tag_name_list.update(SURVEY_PURPOSE_MAPPING.get(p, []))

        # 태그 벡터 계산
        tag_vec = self._get_tag_vector(list(tag_name_list))

        # 사용자가 선택한 책 벡터 평균
        book_vec = np.zeros(self.model.item_embeddings.shape[1])

        if book_idx_list:
            internal_idx_list = [
                self.item_map[b] for b in book_idx_list if b in self.item_map
            ]
            if internal_idx_list:
                book_vec = self.all_item_vectors[internal_idx_list].mean(axis=0)

            exclude_set.update(book_idx_list)

        if np.all(tag_vec == 0) and np.all(book_vec == 0):
            return []

        if np.all(tag_vec == 0):
            hybrid_vec = book_vec
        elif np.all(book_vec == 0):
            hybrid_vec = tag_vec
        else:
            hybrid_vec = 0.4 * tag_vec + 0.6 * book_vec

        scores = self._compute_cosine_scores(hybrid_vec)

        return self._format_results(scores, k, exclude_indices=exclude_set)

    # -----------------------------------------------------------------
    # 인기 top10 추천
    # -----------------------------------------------------------------
    def _recommend_popular(self, exclude_indices: list[int] = []):
        k = 10

        exclude_set = set(exclude_indices)

        sql = """
            SELECT 
                b.idx AS book_idx,
                COUNT(r.rating) AS rating_count,
                AVG(r.rating) AS avg_rating
            FROM book_tb b
            JOIN book_rating_tb r ON b.idx = r.book_idx
            WHERE r.deleted_at IS NULL
            GROUP BY b.idx
            HAVING COUNT(r.rating) >= 3
            ORDER BY rating_count DESC, avg_rating DESC
        """

        try:
            df = pd.read_sql(sql, self.engine)
        except Exception as e:
            print(f"Popular Books Query Error: {e}")
            return []

        results, used = [], set()

        for _, row in df.iterrows():
            bidx = int(row["book_idx"])

            if bidx in exclude_set or bidx in used:
                continue

            scores = float(row["rating_count"]) * float(row["avg_rating"])
            results.append({"book_idx": bidx, "score": scores})

            used.add(bidx)
            exclude_set.add(bidx)

            if len(results) >= k:
                break

        return results

    # -----------------------------------------------------------------
    # 장르별 top10 추천
    # -----------------------------------------------------------------
    def _recommend_single_genre(self, genre_name: str, exclude_indices: list[int] = []):
        k = 10
        exclude_set = set(exclude_indices)

        if genre_name not in SURVEY_GENRE_MAPPING:
            return []

        tag_list = SURVEY_GENRE_MAPPING[genre_name]

        tag_vec = self._get_tag_vector(tag_list)
        if np.all(tag_vec == 0):
            return []

        scores = self._compute_cosine_scores(tag_vec)

        return self._format_results(scores, k, exclude_indices=exclude_set)

    # -----------------------------------------------------------------
    # 전체 장르 섹션
    # -----------------------------------------------------------------
    def _recommend_genre(self, exclude_indices: list[int] = []):
        exclude_set = set(exclude_indices)
        section_list = []

        for genre in GENRE_SECTION_ORDER:
            book_list = self._recommend_single_genre(genre, exclude_set)
            exclude_set.update([b["book_idx"] for b in book_list])

            section_list.append({"genre": genre, "book_list": book_list})

        return section_list

    # -----------------------------------------------------------------
    # 메인 home 추천 함수
    # -----------------------------------------------------------------
    def get_home_recommend(
        self,
        user_idx: int,
    ):
        warm, recent_available = self._get_user_status(user_idx)

        is_user_in_model = user_idx in self.user_map

        use_warm_logic = warm and is_user_in_model

        exclude_set = set()
        response = {}

        if use_warm_logic:
            top1 = self._recommend_personal_top1(user_idx)
            if top1:
                exclude_set.add(top1["book_idx"])
            response["top1"] = top1

            top10 = self._recommend_personal(
                user_idx, exclude_indices=list(exclude_set)
            )
            exclude_set.update([b["book_idx"] for b in top10])
            response["top10"] = top10

        else:
            genre_list, mood_list, purpose_list, book_idx_list = (
                self._load_survey_response(user_idx)
            )

            top1 = self._recommend_initial_top1(
                genre_list,
                mood_list,
                purpose_list,
                book_idx_list,
            )
            if top1:
                exclude_set.add(top1["book_idx"])
            response["top1"] = top1

            top10 = self._recommend_initial(
                genre_list,
                mood_list,
                purpose_list,
                book_idx_list,
                exclude_indices=list(exclude_set),
            )
            exclude_set.update([b["book_idx"] for b in top10])
            response["top10"] = top10

        if recent_available:
            recent_top10 = self._recommend_recent(
                user_idx, exclude_indices=list(exclude_set)
            )
            exclude_set.update([b["book_idx"] for b in recent_top10])
            response["recent_top10"] = recent_top10
        else:
            response["recent_top10"] = []

        popular_top10 = self._recommend_popular(exclude_indices=list(exclude_set))
        exclude_set.update([b["book_idx"] for b in popular_top10])
        response["popular_top10"] = popular_top10

        response["genre_section_list"] = self._recommend_genre(
            exclude_indices=list(exclude_set)
        )

        return response
