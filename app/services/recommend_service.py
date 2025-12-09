import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from app.loaders.model_loader import light
from app.config.settings import settings
from app.constants.constants import (
    SURVEY_GENRE_MAPPING,
    SURVEY_MOOD_MAPPING,
    SURVEY_PURPOSE_MAPPING,
    GENRE_SECTION_ORDER,
)


class RecommendService:
    def __init__(self):
        self.model = light.model
        self.item_features = light.item_features

        self.item_map = light.item_id_map
        self.rev_item_map = light.rev_item_id_map
        self.user_map = light.user_id_map
        self.rev_user_map = light.rev_user_id_map

        self.engine = create_engine(settings.DATABASE_URL)

        self.all_item_vectors = self.item_features.dot(self.model.item_embeddings)

    # ============================================================================
    # [helper] 순수 top-k 함수
    # ============================================================================
    def _select_top_k(
        self, scores, k, exclude_indices, idx_map=None, key_name="book_idx"
    ):
        if idx_map is None:
            idx_map = self.rev_item_map

        excluded = set(exclude_indices)
        ranked = np.argsort(-scores)

        results = []
        used = set()
        picked_internal = []

        for internal_id in ranked:
            real_id = idx_map.get(internal_id)
            if real_id is None:
                continue

            if real_id in excluded:
                continue

            if real_id in used:
                continue

            results.append({key_name: real_id})
            picked_internal.append(internal_id)
            used.add(real_id)

            if len(results) >= k:
                break

        return results, picked_internal

    # ============================================================================
    # [helper] TAG → vector 변환
    # ============================================================================
    def _get_tag_vector(self, tag_name_list):
        if not tag_name_list:
            return np.zeros(self.model.item_embeddings.shape[1])

        lower_tags = [t.lower() for t in tag_name_list]

        placeholders = ", ".join(f":tag_{i}" for i in range(len(lower_tags)))
        params = {f"tag_{i}": t for i, t in enumerate(lower_tags)}

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

            internal_ids = [
                self.item_map[b] for b in df["book_idx"].tolist() if b in self.item_map
            ]

            if internal_ids:
                return self.all_item_vectors[internal_ids].mean(axis=0)
        except:
            pass

        return np.zeros(self.model.item_embeddings.shape[1])

    # ============================================================================
    # [helper] 코사인 유사도 계산
    # ============================================================================
    def _compute_cosine_scores(self, target_vec):
        if np.all(target_vec == 0):
            return np.zeros(self.all_item_vectors.shape[0])

        norms = np.linalg.norm(self.all_item_vectors, axis=1)
        tnorm = np.linalg.norm(target_vec)

        denom = norms * tnorm
        denom[denom == 0] = 1e-9

        return self.all_item_vectors.dot(target_vec) / denom

    # ============================================================================
    # [helper] 유저 warm, recent 판단
    # ============================================================================
    def _get_user_status(self, user_idx):
        rating_sql = "SELECT COUNT(*) AS cnt FROM book_rating_tb WHERE user_idx = :u AND deleted_at IS NULL"
        progress_sql = """
            SELECT SUM(cnt) AS cnt FROM (
                SELECT COUNT(*) AS cnt
                FROM my_book_progress_tb WHERE user_idx = :u AND progress >= 0.2
                UNION ALL
                SELECT COUNT(*) AS cnt
                FROM party_book_progress_tb WHERE user_idx = :u AND progress >= 0.2
            ) t
        """

        warm, recent = False, False

        try:
            df_r = pd.read_sql(text(rating_sql), self.engine, params={"u": user_idx})
            warm = int(df_r["cnt"][0]) >= 3
        except:
            pass

        try:
            df_p = pd.read_sql(text(progress_sql), self.engine, params={"u": user_idx})
            recent = int(df_p["cnt"][0]) >= 1
        except:
            pass

        return warm, recent

    # ============================================================================
    # [helper] 설문 응답 불러오기
    # ============================================================================
    def _load_survey_response(self, user_idx):
        sql = text(
            """
            SELECT Q.idx AS qid, O.idx AS oid, O.book_idx
            FROM survey_response_tb R
            JOIN survey_option_tb O ON R.option_idx = O.idx
            JOIN survey_question_tb Q ON Q.idx = O.question_idx
            WHERE R.user_idx = :uid
        """
        )

        df = pd.read_sql(sql, self.engine, params={"uid": user_idx})

        genre, mood, purpose, books = [], [], [], []

        for _, row in df.iterrows():
            if row["qid"] == 1:
                genre.append(row["oid"])
            elif row["qid"] == 2:
                mood.append(row["oid"])
            elif row["qid"] == 3:
                purpose.append(row["oid"])
            elif row["qid"] == 4 and row["book_idx"]:
                books.append(int(row["book_idx"]))

        return genre, mood, purpose, books

    # ============================================================================
    # 개인화 추천 (11개)
    # ============================================================================
    def _recommend_personal_11(self, user_idx, exclude):
        if user_idx not in self.user_map:
            return []

        internal = self.user_map[user_idx]
        scores = self.model.predict(
            internal,
            item_ids=np.arange(self.item_features.shape[0]),
            item_features=self.item_features,
        )

        results, _ = self._select_top_k(scores, 11, exclude)
        return results

    # ============================================================================
    # 개인화 top1 + top10 분리
    # ============================================================================
    def _personal_top1_top10(self, user_idx, exclude):
        top11 = self._recommend_personal_11(user_idx, exclude)

        if not top11:
            return {}, []

        top1 = top11[0]
        top10 = top11[1:]

        exclude.add(top1["book_idx"])
        exclude.update(b["book_idx"] for b in top10)

        return top1, top10

    # ============================================================================
    # 설문 기반 초기 추천 (11개)
    # ============================================================================
    def _initial_recommend_11(self, user_idx, exclude):
        genre, mood, purpose, books = self._load_survey_response(user_idx)

        tag_names = set()

        def extract(mapping, keys):
            for k in keys:
                if k in mapping:
                    tag_names.update(mapping[k])

        extract(SURVEY_GENRE_MAPPING, genre)
        extract(SURVEY_MOOD_MAPPING, mood)
        extract(SURVEY_PURPOSE_MAPPING, purpose)

        tag_vec = self._get_tag_vector(tag_names)

        book_vec = np.zeros(self.model.item_embeddings.shape[1])
        if books:
            internal_ids = [self.item_map[b] for b in books if b in self.item_map]
            if internal_ids:
                book_vec = self.all_item_vectors[internal_ids].mean(axis=0)

        if np.all(tag_vec == 0) and np.all(book_vec == 0):
            return []

        if np.all(book_vec == 0):
            target = tag_vec
        elif np.all(tag_vec == 0):
            target = book_vec
        else:
            target = 0.4 * tag_vec + 0.6 * book_vec

        scores = self._compute_cosine_scores(target)

        results, _ = self._select_top_k(scores, 11, exclude)
        return results

    # ============================================================================
    # 설문 기반 top1 + top10 분리
    # ============================================================================
    def _initial_top1_top10(self, user_idx, exclude):
        _, _, _, books = self._load_survey_response(user_idx)
        exclude.update(books)

        results = self._initial_recommend_11(user_idx, exclude)

        if not results:
            return {}, []

        top1 = results[0]
        top10 = results[1:]

        exclude.add(top1["book_idx"])
        exclude.update(b["book_idx"] for b in top10)

        return top1, top10

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

        results, _ = self._select_top_k(
            scores,
            k,
            exclude_indices={user_idx},
            idx_map=self.rev_user_map,
            key_name="user_idx",
        )

        return results

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

        results, _ = self._select_top_k(scores, k, exclude_indices=exclude_set)

        return results

    # ============================================================================
    # recent 추천
    # ============================================================================
    def _home_recent(self, user_idx, exclude):
        sql = text(
            """
            SELECT book_idx FROM (
                SELECT book_idx, updated_at
                FROM my_book_progress_tb
                WHERE user_idx = :u AND progress >= 0.2
                UNION ALL
                SELECT p.book_idx, pbp.updated_at
                FROM party_book_progress_tb pbp
                JOIN party_tb p ON pbp.party_idx = p.idx
                WHERE pbp.user_idx = :u AND pbp.progress >= 0.2
            ) t ORDER BY updated_at DESC LIMIT 1
            """
        )

        df = pd.read_sql(sql, self.engine, params={"u": user_idx})

        if df.empty or pd.isna(df["book_idx"][0]):
            return None

        recent_book = int(df["book_idx"][0])
        exclude.add(recent_book)

        recommended = self.recommend_similar_book(recent_book, 10, exclude)

        return [
            {
                "bookIdx": recent_book,
                "bookList": [{"bookIdx": r["book_idx"]} for r in recommended],
            }
        ]

    # ============================================================================
    # popular
    # ============================================================================
    def _home_popular(self, exclude):
        sql = """
            SELECT b.idx AS book_idx, COUNT(*) AS c, AVG(r.rating) AS a
            FROM book_tb b
            JOIN book_rating_tb r ON b.idx = r.book_idx
            WHERE r.deleted_at IS NULL
            GROUP BY b.idx
            HAVING COUNT(*) >= 3
            ORDER BY c DESC, a DESC
        """

        df = pd.read_sql(sql, self.engine)
        result = []

        for _, row in df.iterrows():
            b = int(row["book_idx"])
            if b in exclude:
                continue
            result.append({"book_idx": b})
            exclude.add(b)
            if len(result) >= 10:
                break

        return result

    # ============================================================================
    # genre section
    # ============================================================================
    def _home_genre(self, exclude):
        sections = []

        for genre in GENRE_SECTION_ORDER:
            tags = SURVEY_GENRE_MAPPING.get(genre, [])
            vec = self._get_tag_vector(tags)

            if np.all(vec == 0):
                sections.append({"genre": genre, "book_list": []})
                continue

            scores = self._compute_cosine_scores(vec)
            books, _ = self._select_top_k(scores, 10, exclude)

            exclude.update(b["book_idx"] for b in books)
            sections.append({"genre": genre, "book_list": books})

        return sections

    # ============================================================================
    # 메인: 홈 추천
    # ============================================================================
    def get_home_recommend(self, user_idx):
        warm, recent = self._get_user_status(user_idx)
        is_user_in_model = user_idx in self.user_map

        exclude = set()

        if warm and is_user_in_model:
            top1, top10 = self._personal_top1_top10(user_idx, exclude)
        else:
            top1, top10 = self._initial_top1_top10(user_idx, exclude)

        recent_top10 = self._home_recent(user_idx, exclude)

        if not recent_top10:
            recent_top10 = None

        popular_top10 = self._home_popular(exclude)
        genre_section_list = self._home_genre(exclude)

        return {
            "top1": top1,
            "top10": top10,
            "recentTop10": recent_top10,
            "popularTop10": popular_top10,
            "genreSectionList": genre_section_list,
        }
