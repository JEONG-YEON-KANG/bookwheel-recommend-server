from app.core.constants import (
    SURVEY_GENRE_MAPPING,
    SURVEY_MOOD_MAPPING,
    SURVEY_PURPOSE_MAPPING,
)
import pandas as pd
from sqlalchemy import create_engine, text
import os
import sys
from dotenv import load_dotenv
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# --- 환경 설정 ---
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("[ERROR] DATABASE_URL is not set in environment variables.")

engine = create_engine(DATABASE_URL)

# --- 파일 경로 설정 ---
CSV_DIR = os.path.join(project_root, "goodbooks-10k")

RATINGS_FILE = os.path.join(CSV_DIR, "ratings.csv")
BOOKS_FILE = os.path.join(CSV_DIR, "books.csv")
TAGS_FILE = os.path.join(CSV_DIR, "tags.csv")
BOOK_TAGS_FILE = os.path.join(CSV_DIR, "book_tags.csv")


# ===========================================================================
# 설문조사 질문 및 옵션 구성
# ===========================================================================

survey_questions = [
    "주로 어떤 내용의 책에 손이 가시나요?",  # 장르
    "책을 통해 어떤 기분을 느끼고 싶으신가요?",  # 분위기
    "책을 통해 주로 무엇을 얻고 싶으신가요?",  # 목적
    "최근에 감명 깊게 읽은 책은 무엇인가요?",  # 도서 선택
]

SURVEY_BOOK_IDX_LIST = [2, 9, 4, 10, 15, 374]

survey_options_list = [
    list(SURVEY_GENRE_MAPPING.keys()),
    list(SURVEY_MOOD_MAPPING.keys()),
    list(SURVEY_PURPOSE_MAPPING.keys()),
    SURVEY_BOOK_IDX_LIST,
]


# ===========================================================================
# 1. CSV 데이터 시딩 함수
# ===========================================================================


def clean_isbn(val):
    if pd.isna(val):
        return None
    s = str(val).strip().replace(".0", "")[:13]
    return s if s else None


def seed_fake_users(engine, user_count: int):
    print("[INFO] Seeding fake users...")
    users = pd.DataFrame({"nickname": [f"user_{i}" for i in range(1, user_count + 1)]})
    users.to_sql("user_tb", engine, if_exists="append", index=False, chunksize=5000)


def seed_books(engine):
    print("[INFO] Seeding books...")
    if not os.path.exists(BOOKS_FILE):
        print(f"[ERROR] File not found: {BOOKS_FILE}")
        return

    df = pd.read_csv(BOOKS_FILE)
    df = df.rename(
        columns={
            "book_id": "idx",
            "title": "title",
            "authors": "author",
            "original_publication_year": "publication_year",
            "language_code": "language_code",
            "average_rating": "average_rating",
            "ratings_count": "ratings_count",
            "publisher": "publisher",
            "isbn13": "isbn13",
            "description": "description",
            "image_url": "cover_image_path",
        }
    )

    df["publisher"] = df["publisher"].fillna("")
    df["description"] = df["description"].fillna("")
    df["language_code"] = df["language_code"].fillna("")
    df["book_file_path"] = "/default/path/book.epub"
    df["isbn13"] = df["isbn13"].apply(clean_isbn)
    df.loc[df["isbn13"] == "", "isbn13"] = None

    cols = [
        "idx",
        "title",
        "author",
        "publisher",
        "publication_year",
        "description",
        "book_file_path",
        "cover_image_path",
        "average_rating",
        "ratings_count",
        "language_code",
        "isbn13",
    ]
    df[cols].to_sql("book_tb", engine, if_exists="append", index=False, chunksize=10000)


def seed_tags(engine):
    print("[INFO] Seeding tags...")
    df = pd.read_csv(TAGS_FILE)
    df = df.rename(columns={"Genre ID": "idx", "Genre Name": "name"})
    df.to_sql("tag_tb", engine, if_exists="append", index=False)


def seed_book_tags(engine):
    print("[INFO] Seeding book_tags...")
    df = pd.read_csv(BOOK_TAGS_FILE)
    df = df.rename(columns={"book_id": "book_idx", "genre_id": "tag_idx"})
    df[["book_idx", "tag_idx"]].to_sql(
        "book_tag_tb", engine, if_exists="append", index=False, chunksize=10000
    )


def seed_ratings(engine):
    print("[INFO] Seeding ratings...")
    df = pd.read_csv(RATINGS_FILE)
    df = df.rename(
        columns={"user_id": "user_idx", "book_id": "book_idx", "rating": "rating"}
    )

    valid_books = pd.read_sql("SELECT idx FROM book_tb", engine)["idx"].tolist()
    valid_books_set = set(valid_books)
    df = df[df["book_idx"].isin(valid_books_set)]

    df[["user_idx", "book_idx", "rating"]].to_sql(
        "book_rating_tb", engine, if_exists="append", index=False, chunksize=20000
    )


# ===========================================================================
# 2. 설문조사 데이터 시딩 함수
# ===========================================================================


def seed_survey_questions(engine):
    print("[INFO] Seeding survey questions...")
    df = pd.DataFrame({"content": survey_questions})
    df.to_sql("survey_question_tb", engine, if_exists="append", index=False)


def seed_survey_options(engine):
    print("[INFO] Seeding survey options...")

    df_q = pd.read_sql(
        "SELECT idx, content FROM survey_question_tb ORDER BY idx", engine
    )

    if df_q.empty:
        print("[ERROR] No questions found! Skipping options.")
        return

    insert_rows = []

    q_idx_list = df_q["idx"].tolist()

    for i, options in enumerate(survey_options_list):
        if i >= len(q_idx_list):
            break
        qid = int(q_idx_list[i])

        if i == 3:
            for book_idx in options:
                insert_rows.append({"question_idx": qid, "book_idx": book_idx})
        else:
            for opt_text in options:
                insert_rows.append({"question_idx": qid, "content": opt_text})

    df = pd.DataFrame(insert_rows)
    df.to_sql("survey_option_tb", engine, if_exists="append", index=False)


def seed_survey_option_tags(engine):
    print("[INFO] Seeding survey option-tag mappings...")

    tags_df = pd.read_sql("SELECT idx, name FROM tag_tb", engine)
    tag_map = {name.lower(): idx for idx, name in zip(tags_df["idx"], tags_df["name"])}

    options_df = pd.read_sql(
        "SELECT idx, content FROM survey_option_tb WHERE content is NOT NULL", engine
    )

    ALL_MAPPINGS = {
        **SURVEY_GENRE_MAPPING,
        **SURVEY_MOOD_MAPPING,
        **SURVEY_PURPOSE_MAPPING,
    }

    insert_rows = []
    for _, row in options_df.iterrows():
        option_id = row["idx"]
        option_text = row["content"]
        target_tags = ALL_MAPPINGS.get(option_text, [])

        for tag_name in target_tags:
            tag_id = tag_map.get(tag_name.lower())
            if tag_id:
                insert_rows.append({"option_idx": option_id, "tag_idx": tag_id})

    if not insert_rows:
        print("[WARN] No mappings to insert!")
        return

    df = pd.DataFrame(insert_rows)
    df.to_sql("survey_option_tag_tb", engine, if_exists="append", index=False)


def seed_recent_users(engine, start_user=1, end_user=20):
    book_df = pd.read_sql("SELECT idx FROM book_tb", engine)
    book_idx_list = book_df["idx"].tolist()

    rows = []

    for user_idx in range(start_user, end_user + 1):

        book_idx = int(np.random.choice(book_idx_list))
        progress_val = float(np.random.uniform(0.3, 0.8))

        rows.append(
            {
                "user_idx": user_idx,
                "book_idx": book_idx,
                "progress": progress_val,
                "current_cfi_position": "/6/2[chapter1]!/4/12",
                "updated_at": pd.Timestamp.utcnow(),
            }
        )

    df = pd.DataFrame(rows)
    df.to_sql("my_book_progress_tb", engine, if_exists="append", index=False)


# ===========================================================================
# 3. 메인 실행
# ===========================================================================
if __name__ == "__main__":

    for f in [BOOKS_FILE, TAGS_FILE, BOOK_TAGS_FILE, RATINGS_FILE]:
        if not os.path.exists(f):
            print(f"[ERROR] Missing file: {f}")
            exit()

    print("\n🚀 Starting Database Reset & Seed...\n")

    # 1. 초기화 (설문 데이터만 초기화하려면 여기만 수정하세요!)
    with engine.connect() as conn:
        print("[INFO] Clearing existing data...")
        conn.execute(
            text(
                "TRUNCATE TABLE book_rating_tb, book_tag_tb, survey_option_tag_tb, survey_option_tb, survey_question_tb, tag_tb, book_tb, user_tb RESTART IDENTITY CASCADE;"
            )
        )
        conn.commit()

    # 2. 기본 데이터
    try:
        max_user_idx = pd.read_csv(RATINGS_FILE)["user_id"].max()
    except:
        max_user_idx = 100

    seed_fake_users(engine, max_user_idx)
    seed_books(engine)
    seed_tags(engine)
    seed_book_tags(engine)
    seed_ratings(engine)

    # 3. 설문 데이터
    seed_survey_questions(engine)
    seed_survey_options(engine)
    seed_survey_option_tags(engine)

    seed_recent_users(engine, 1, 20)

    print("\n All Done! Database seeding completed successfully.\n")
