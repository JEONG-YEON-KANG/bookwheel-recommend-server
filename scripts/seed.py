# ======================================================================
#  BookWheel SEED SCRIPT
# ======================================================================

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
from datetime import datetime, timedelta, timezone
import random

# ----------------------------------------------------------------------
# 경로 설정
# ----------------------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("[ERROR] DATABASE_URL is not set.")

engine = create_engine(DATABASE_URL)

CSV_DIR = os.path.join(project_root, "dataset")
BOOKS_FILE = os.path.join(CSV_DIR, "books.csv")
RATINGS_FILE = os.path.join(CSV_DIR, "ratings.csv")
TAGS_FILE = os.path.join(CSV_DIR, "tags.csv")
BOOK_TAGS_FILE = os.path.join(CSV_DIR, "book_tags.csv")


# ----------------------------------------------------------------------
# 유틸
# ----------------------------------------------------------------------
def now_ts():
    return datetime.now(timezone.utc)


def clean_isbn(val):
    if pd.isna(val):
        return None
    s = str(val).strip().replace(".0", "")[:13]
    return s if s else None


def random_datetime_within(days=7):
    now = datetime.now(timezone.utc)
    delta = timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return now - delta


# ----------------------------------------------------------------------
# 설문 구성
# ----------------------------------------------------------------------
survey_questions = [
    "주로 어떤 내용의 책에 손이 가시나요?",
    "책을 통해 어떤 기분을 느끼고 싶으신가요?",
    "책을 통해 주로 무엇을 얻고 싶으신가요?",
    "최근에 감명 깊게 읽은 책은 무엇인가요?",
]

SURVEY_BOOK_IDX_LIST = [2, 9, 4, 10, 15, 374]

survey_options_list = [
    list(SURVEY_GENRE_MAPPING.keys()),
    list(SURVEY_MOOD_MAPPING.keys()),
    list(SURVEY_PURPOSE_MAPPING.keys()),
    SURVEY_BOOK_IDX_LIST,
]

DEMO_USERS = [602, 415, 1278]


# ======================================================================
# 1. TRUNCATE (DDL 기반 전체 초기화)
# ======================================================================
def reset_database(engine):
    print("[RESET] Truncating all tables...")

    TRUNCATE_SQL = """
    TRUNCATE TABLE 
      book_comment_tb,
      book_highlight_tb,
      party_book_progress_tb,
      party_members_tb,
      party_tb,
      message_tb,
      friend_tb,
      book_review_tb,
      my_book_progress_tb,
      to_read_tb,
      book_rating_tb,
      book_tag_tb,
      survey_option_tag_tb,
      survey_option_tb,
      survey_question_tb,
      tag_tb,
      book_tb,
      user_basic_tb,
      user_social_tb,
      user_tb
    RESTART IDENTITY CASCADE;
    """

    with engine.connect() as conn:
        conn.execute(text(TRUNCATE_SQL))
        conn.commit()

    print("[RESET] Done.\n")


# ======================================================================
# 2. 기본 데이터 삽입
# ======================================================================
def seed_fake_users(engine, max_user_idx):
    print("[SEED] Users...")

    # ---------------------------------------
    # 1) 데모 유저 정의
    # ---------------------------------------
    demo_users = pd.DataFrame(
        [
            {
                "idx": 602,
                "nickname": "로맨스덕후",
                "profile_image_path": "/images/profile/default1.png",
                "type": "BASIC",
                "age": 24,
                "gender": "F",
                "created_at": now_ts(),
                "deleted_at": None,
            },
            {
                "idx": 415,
                "nickname": "SF매니아",
                "profile_image_path": "/images/profile/default2.png",
                "type": "BASIC",
                "age": 27,
                "gender": "M",
                "created_at": now_ts(),
                "deleted_at": None,
            },
            {
                "idx": 1278,
                "nickname": "미스터리냥",
                "profile_image_path": "/images/profile/default3.png",
                "type": "BASIC",
                "age": 22,
                "gender": "F",
                "created_at": now_ts(),
                "deleted_at": None,
            },
        ]
    )

    demo_basic = pd.DataFrame(
        [
            {
                "user_idx": 602,
                "id": "demo602",
                "password": "test1234!",
                "email": "demo602@bookwheel.com",
            },
            {
                "user_idx": 415,
                "id": "demo415",
                "password": "test1234!",
                "email": "demo415@bookwheel.com",
            },
            {
                "user_idx": 1278,
                "id": "demo1278",
                "password": "test1234!",
                "email": "demo1278@bookwheel.com",
            },
        ]
    )

    # ---------------------------------------
    # 2) 일반 유저 idx 생성 (데모 유저 제외)
    # ---------------------------------------
    all_possible_ids = range(1, max_user_idx + 1)

    normal_ids = [i for i in all_possible_ids if i not in DEMO_USERS]

    normal_users = pd.DataFrame(
        {
            "idx": normal_ids,
            "nickname": [f"user_{i}" for i in normal_ids],
            "profile_image_path": [None] * len(normal_ids),
            "type": ["BASIC"] * len(normal_ids),
            "age": [random.randint(18, 40) for _ in normal_ids],
            "gender": [random.choice(["M", "F"]) for _ in normal_ids],
            "created_at": [now_ts()] * len(normal_ids),
            "deleted_at": [None] * len(normal_ids),
        }
    )

    # ---------------------------------------
    # 3) DB 저장
    # ---------------------------------------
    # 1) 일반 유저 먼저
    normal_users.to_sql("user_tb", engine, if_exists="append", index=False)

    # 2) 데모 유저
    demo_users.to_sql("user_tb", engine, if_exists="append", index=False)
    demo_basic.to_sql("user_basic_tb", engine, if_exists="append", index=False)

    print(f"[OK] Normal users: {len(normal_users)}  Demo users: 3")

    # ---------------------------------------
    # 4) 마지막으로 sequence 위치를 MAX(idx)+1
    # ---------------------------------------
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            SELECT setval('user_tb_idx_seq', (SELECT MAX(idx) FROM user_tb) + 1);
        """
            )
        )
        conn.commit()


def seed_books(engine):
    print("[SEED] Books...")
    df = pd.read_csv(BOOKS_FILE)

    df = df.rename(
        columns={
            "book_id": "idx",
            "title": "title",
            "authors": "author",
            "publisher": "publisher",
            "description": "description",
            "original_publication_year": "publication_year",
            "language_code": "language_code",
            "average_rating": "average_rating",
            "ratings_count": "ratings_count",
            "image_url": "cover_image_path",
            "isbn13": "isbn13",
        }
    )

    df["publisher"] = df["publisher"].fillna("")
    df["description"] = df["description"].fillna("")
    df["language_code"] = df["language_code"].fillna("")
    df["book_file_path"] = "/default/book.epub"
    df["isbn13"] = df["isbn13"].apply(clean_isbn)

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

    df[cols].to_sql("book_tb", engine, if_exists="append", index=False, chunksize=5000)


def seed_tags(engine):
    print("[SEED] Tags...")
    df = pd.read_csv(TAGS_FILE)
    df = df.rename(columns={"Genre ID": "idx", "Genre Name": "name"})
    df.to_sql("tag_tb", engine, if_exists="append", index=False)


def seed_book_tags(engine):
    print("[SEED] Book Tags...")
    df = pd.read_csv(BOOK_TAGS_FILE)
    df = df.rename(columns={"book_id": "book_idx", "genre_id": "tag_idx"})
    df.to_sql("book_tag_tb", engine, if_exists="append", index=False, chunksize=5000)


def seed_ratings(engine):
    print("[SEED] Ratings...")
    df = pd.read_csv(RATINGS_FILE)
    df = df.rename(
        columns={"book_id": "book_idx", "user_id": "user_idx", "rating": "rating"}
    )

    valid_books = set(pd.read_sql("SELECT idx FROM book_tb", engine)["idx"].tolist())
    df = df[df["book_idx"].isin(valid_books)]

    df[["user_idx", "book_idx", "rating"]].to_sql(
        "book_rating_tb", engine, if_exists="append", index=False, chunksize=20000
    )


# ======================================================================
# 3. Survey
# ======================================================================
def seed_survey_questions(engine):
    print("[SEED] Survey Questions...")
    df = pd.DataFrame({"content": survey_questions})
    df.to_sql("survey_question_tb", engine, if_exists="append", index=False)


def seed_survey_options(engine):
    print("[SEED] Survey Options...")

    q_df = pd.read_sql("SELECT idx FROM survey_question_tb ORDER BY idx", engine)
    qids = q_df["idx"].tolist()

    insert_rows = []

    for i, options in enumerate(survey_options_list):
        qid = qids[i]

        if i == 3:  # book choices
            for book_idx in options:
                insert_rows.append({"question_idx": qid, "book_idx": book_idx})
        else:
            for opt_text in options:
                insert_rows.append({"question_idx": qid, "content": opt_text})

    pd.DataFrame(insert_rows).to_sql(
        "survey_option_tb", engine, if_exists="append", index=False
    )


def seed_survey_option_tags(engine):
    print("[SEED] Survey Option Tags...")

    tags_df = pd.read_sql("SELECT idx, name FROM tag_tb", engine)
    tag_map = {name.lower(): idx for idx, name in zip(tags_df["idx"], tags_df["name"])}

    options_df = pd.read_sql(
        "SELECT idx, content FROM survey_option_tb WHERE content IS NOT NULL",
        engine,
    )

    ALL_MAP = {**SURVEY_GENRE_MAPPING, **SURVEY_MOOD_MAPPING, **SURVEY_PURPOSE_MAPPING}

    rows = []
    for _, row in options_df.iterrows():
        opt_idx = row["idx"]
        opt_text = row["content"]

        if opt_text in ALL_MAP:
            for tag_name in ALL_MAP[opt_text]:
                tid = tag_map.get(tag_name.lower())
                if tid:
                    rows.append({"option_idx": opt_idx, "tag_idx": tid})

    if rows:
        pd.DataFrame(rows).to_sql(
            "survey_option_tag_tb", engine, if_exists="append", index=False
        )


def seed_demo_survey_responses(engine):
    print("[SEED] Demo Survey Responses...")

    q_df = pd.read_sql("SELECT idx FROM survey_question_tb ORDER BY idx", engine)
    q1, q2, q3, q4 = q_df["idx"].tolist()

    opt_df = pd.read_sql(
        "SELECT idx, question_idx, content FROM survey_option_tb", engine
    )

    def get_opt(qid, text):
        r = opt_df[(opt_df["question_idx"] == qid) & (opt_df["content"] == text)]
        return int(r["idx"].iloc[0])

    DEMO_GENRE = {602: "로맨스", 415: "SF", 1278: "미스터리/스릴러"}
    DEMO_MOOD = {602: "#가슴_따뜻한", 415: "#긴장감_넘치는", 1278: "#긴장감_넘치는"}
    DEMO_PURPOSE = {
        602: "따뜻한 위로와 감동",
        415: "스트레스 해소",
        1278: "재미와 교양 쌓기",
    }

    rows = []

    for u in DEMO_USERS:
        rows.append({"user_idx": u, "option_idx": get_opt(q1, DEMO_GENRE[u])})
        rows.append({"user_idx": u, "option_idx": get_opt(q2, DEMO_MOOD[u])})
        rows.append({"user_idx": u, "option_idx": get_opt(q3, DEMO_PURPOSE[u])})

    pd.DataFrame(rows).to_sql(
        "survey_response_tb", engine, if_exists="append", index=False
    )


# ======================================================================
# 4. Demo User Activity
# ======================================================================
def seed_demo_recent_progress(engine):
    print("[SEED] Demo Recent Reading Progress...")

    DEMO_RECENT = {
        602: [8854, 1308, 3241],
        415: [2527, 2149, 8187],
        1278: [9470, 2081, 1602],
    }

    rows = []
    now = datetime.now(timezone.utc)

    for u, book_list in DEMO_RECENT.items():
        offsets = [
            timedelta(hours=random.randint(0, 2)),
            timedelta(hours=random.randint(4, 12)),
            timedelta(days=random.randint(1, 3)),
        ]

        for i, b in enumerate(book_list):
            rows.append(
                {
                    "user_idx": u,
                    "book_idx": b,
                    "progress": round(random.uniform(0.2, 0.9), 3),
                    "current_cfi_position": f"/6/2[chap{i}]!/4/{i}",
                    "updated_at": now - offsets[i],
                }
            )

    pd.DataFrame(rows).to_sql(
        "my_book_progress_tb", engine, if_exists="append", index=False
    )


def seed_reviews(engine):
    print("[SEED] Demo BookReviews...")

    sample_reviews = [
        "정말 감명 깊게 읽은 책입니다. 추천!",
        "스토리가 흥미진진하고 캐릭터가 좋아요.",
        "조금 어려웠습니다.",
        "배울 점이 많네요.",
    ]

    rows = []

    for u in DEMO_USERS:
        df = pd.read_sql(
            f"SELECT book_idx FROM my_book_progress_tb WHERE user_idx={u}", engine
        )

        for b in df["book_idx"].tolist()[:2]:
            rows.append(
                {
                    "user_idx": u,
                    "book_idx": int(b),
                    "content": random.choice(sample_reviews),
                    "created_at": random_datetime_within(7),
                }
            )

    if rows:
        pd.DataFrame(rows).to_sql(
            "book_review_tb", engine, if_exists="append", index=False
        )


def seed_demo_friends(engine):
    print("[SEED] Demo Friends...")

    rows = [
        {
            "request_user_idx": 602,
            "receive_user_idx": 415,
            "status": "ACCEPTED",
            "created_at": now_ts(),
        },
        {
            "request_user_idx": 602,
            "receive_user_idx": 1278,
            "status": "ACCEPTED",
            "created_at": now_ts(),
        },
    ]

    pd.DataFrame(rows).to_sql("friend_tb", engine, if_exists="append", index=False)


def seed_demo_messages(engine):
    print("[SEED] Demo Messages...")

    messages = ["이 책 읽어봤어?", "추천 고마워!", "재밌더라", "읽어볼게!"]
    pairs = [(602, 415), (415, 1278), (602, 1278)]

    rows = []
    for s, r in pairs:
        for _ in range(2):
            rows.append(
                {
                    "sender_idx": s,
                    "receiver_idx": r,
                    "content": random.choice(messages),
                    "is_read": random.random() < 0.5,
                    "sent_at": random_datetime_within(10),
                }
            )

    pd.DataFrame(rows).to_sql("message_tb", engine, if_exists="append", index=False)


def seed_demo_parties(engine):
    print("[SEED] Demo Parties...")

    popular_books = pd.read_sql(
        "SELECT idx FROM book_tb ORDER BY ratings_count DESC LIMIT 30", engine
    )["idx"].tolist()

    party_rows = []
    member_rows = []
    progress_rows = []

    for u in DEMO_USERS:
        party_rows.append(
            {
                "host_user_idx": u,
                "book_idx": int(random.choice(popular_books)),
                "title": f"{u}님의 독서 파티",
                "description": "함께 읽어요!",
                "max_members": 10,
                "current_members": 1,
                "status": "OPEN",
                "is_private": False,
                "created_at": now_ts(),
            }
        )

    pd.DataFrame(party_rows).to_sql("party_tb", engine, if_exists="append", index=False)

    party_df = pd.read_sql(
        "SELECT idx, host_user_idx FROM party_tb ORDER BY idx DESC LIMIT 3", engine
    )

    for _, row in party_df.iterrows():
        pid = int(row["idx"])
        host = int(row["host_user_idx"])

        # Host auto join
        member_rows.append({"party_idx": pid, "user_idx": host, "status": "ACTIVE"})

        others = [u for u in DEMO_USERS if u != host]
        for j in random.sample(others, random.randint(1, 2)):
            member_rows.append({"party_idx": pid, "user_idx": j, "status": "ACTIVE"})

        for u in DEMO_USERS:
            progress_rows.append(
                {
                    "party_idx": pid,
                    "user_idx": u,
                    "progress": round(random.uniform(0.1, 0.8), 2),
                    "current_cfi_position": "/6/2[last]!/4/12",
                    "updated_at": random_datetime_within(5),
                }
            )

    pd.DataFrame(member_rows).to_sql(
        "party_members_tb", engine, if_exists="append", index=False
    )
    pd.DataFrame(progress_rows).to_sql(
        "party_book_progress_tb", engine, if_exists="append", index=False
    )


# ======================================================================
# MAIN
# ======================================================================
if __name__ == "__main__":
    print("\n BookWheel Database Seeding Started...\n")

    for f in [BOOKS_FILE, RATINGS_FILE, TAGS_FILE, BOOK_TAGS_FILE]:
        if not os.path.exists(f):
            print(f"[ERROR] Missing file: {f}")
            exit()

    reset_database(engine)

    try:
        max_user_idx = pd.read_csv(RATINGS_FILE)["user_id"].max()
    except Exception:
        max_user_idx = 500

    seed_fake_users(engine, max_user_idx)
    seed_books(engine)
    seed_tags(engine)
    seed_book_tags(engine)
    seed_ratings(engine)

    seed_survey_questions(engine)
    seed_survey_options(engine)
    seed_survey_option_tags(engine)
    seed_demo_survey_responses(engine)

    seed_demo_recent_progress(engine)
    seed_reviews(engine)
    seed_demo_friends(engine)
    seed_demo_messages(engine)
    seed_demo_parties(engine)

    print("All Done! Database seeding completed successfully.\n")
