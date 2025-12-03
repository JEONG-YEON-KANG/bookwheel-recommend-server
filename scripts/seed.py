"""
===========================================================
 BookWheel SEED SCRIPT
===========================================================

이 스크립트는 다음을 모두 수행함:

1) 기존 모든 테이블 TRUNCATE + IDENTITY RESET
2) goodbooks-10k 기반 기본 데이터 시드
   - user_tb (fake users)
   - book_tb
   - tag_tb
   - book_tag_tb
   - book_rating_tb
3) 설문(Survey) 데이터 삽입
4) 데모 유저 3명(602, 415, 1278)을 위한 다양한 풍부한 데이터 삽입
   - SurveyResponse
   - MyBookProgress
   - BookReview
   - BookHighlight + BookComment
   - ToRead
   - Friend
   - Message
   - Party + PartyMember
   - PartyBookProgress

===========================================================
"""

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
CSV_DIR = os.path.join(project_root, "dataset")

RATINGS_FILE = os.path.join(CSV_DIR, "ratings.csv")
BOOKS_FILE = os.path.join(CSV_DIR, "books.csv")
TAGS_FILE = os.path.join(CSV_DIR, "tags.csv")
BOOK_TAGS_FILE = os.path.join(CSV_DIR, "book_tags.csv")

# =========================================================================
# 설문조사 질문 및 옵션 구성
# =========================================================================

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

# =========================================================================
# 데모 유저 : 편향된 취향을 가진 대표 유저 3명
# =========================================================================
DEMO_USERS = [602, 415, 1278]


# ===========================================================================
# 유틸 함수
# ===========================================================================
def clean_isbn(val):
    # ISBN 숫자 텍스트를 13자리로 정리
    if pd.isna(val):
        return None
    s = str(val).strip().replace(".0", "")[:13]
    return s if s else None


def random_datetime_within(days: int = 7):
    # 지정된 일수 안에서 랜덤한 과거 날짜 생성
    now = datetime.now(timezone.utc)
    delta = timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return now - delta


# ===========================================================================
# 1. 기본 데이터 삽입
# ===========================================================================
def now_ts():
    return datetime.now(timezone.utc)


def seed_fake_users(engine, max_user_idx):
    print("[INFO] Seeding fake + demo users...")

    # ---------------------------
    # 1) DEMO USERS (3명)
    # ---------------------------
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
                "id": "demoo415",
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

    normal_users = pd.DataFrame(
        {
            "idx": list(range(1, max_user_idx + 1)),
            "nickname": [f"user_{i}" for i in range(1, max_user_idx + 1)],
            "profile_image_path": [None] * max_user_idx,
            "type": ["BASIC"] * max_user_idx,
            "age": [random.randint(18, 40) for _ in range(max_user_idx)],
            "gender": [random.choice(["M", "F"]) for _ in range(max_user_idx)],
            "created_at": [now_ts()] * max_user_idx,
            "deleted_at": [None] * max_user_idx,
        }
    )

    normal_users = normal_users[~normal_users["idx"].isin([602, 415, 1278])]

    all_users = pd.concat([demo_users, normal_users], ignore_index=True)
    all_users.to_sql("user_tb", engine, if_exists="append", index=False)

    demo_basic.to_sql("user_basic_tb", engine, if_exists="append", index=False)

    print(f"[OK] Inserted {len(all_users)} users + {len(demo_basic)} demo basic auths")


def seed_books(engine):
    print("[INFO] Seeding books...")
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


# ===========================================================================
# 3. 데모 유저 시딩
# ===========================================================================


def seed_demo_survey_ressponses(engine):
    print("[INFO] Inserting survey responses for demo users...")

    q_df = pd.read_sql("SELECT idx FROM survey_question_tb ORDER BY idx", engine)
    opt_df = pd.read_sql(
        "SELECT idx, question_idx, content, book_idx FROM survey_option_tb", engine
    )

    # 질문 번호 매핑
    q1, q2, q3, q4 = q_df["idx"].tolist()

    # 데모 유저가 선택할 값
    DEMO_GENRE = {
        602: "로맨스",
        415: "SF",
        1278: "미스터리/스릴러",
    }

    DEMO_MOOD = {602: "#가슴_따뜻한", 415: "#긴장감_넘치는", 1278: "#긴장감_넘치는"}

    DEMO_PURPOSE = {
        602: "따뜻한 위로와 감동",
        415: "스트레스 해소",
        1278: "재미와 교양 쌓기",
    }

    rows = []

    def get_option_idx(qidx, content):
        r = opt_df[(opt_df["question_idx"] == qidx) & (opt_df["content"] == content)]
        if r.empty:
            raise ValueError(
                f"No option found for question {qidx} and content '{content}'"
            )
        return int(r["idx"].iloc[0])

    rows = []

    for u in DEMO_USERS:
        rows.append(
            {
                "user_idx": u,
                "question_idx": q1,
                "option_idx": get_option_idx(q1, DEMO_GENRE[u]),
            }
        )
        rows.append(
            {
                "user_idx": u,
                "question_idx": q2,
                "option_idx": get_option_idx(q2, DEMO_MOOD[u]),
            }
        )
        rows.append(
            {
                "user_idx": u,
                "question_idx": q3,
                "option_idx": get_option_idx(q3, DEMO_PURPOSE[u]),
            }
        )

    pd.DataFrame(rows).to_sql(
        "survey_response_tb", engine, if_exists="append", index=False
    )


def seed_demo_recent_progress(engine):
    print("[SEED] Demo MyBookProgress...")

    DEMO_RECENT = {
        602: [8854, 1308, 3241],
        415: [2527, 2149, 8187],
        1278: [9470, 2081, 1602],
    }

    rows = []
    now = datetime.now(timezone.utc)

    for user_idx, book_list in DEMO_RECENT.items():
        # 시간 간격 (가장 최근 → 가장 오래된)
        offsets = [
            timedelta(hours=random.randint(0, 2)),
            timedelta(hours=random.randint(4, 12)),
            timedelta(days=random.randint(1, 3)),
        ]

        for i, book_idx in enumerate(book_list):
            updated_time = now - offsets[i]
            progress = round(random.uniform(0.2, 0.9), 3)

            rows.append(
                {
                    "user_idx": user_idx,
                    "book_idx": book_idx,
                    "progress": progress,
                    "current_cfi_position": "epubcfi(/6/2[cover]!/4/1:0)",
                    "updated_at": updated_time,
                }
            )

    df = pd.DataFrame(rows)
    df.to_sql("my_book_progress_tb", engine, if_exists="append", index=False)


def seed_reviews(engine):
    print("[SEED] Demo BookReviews...")

    sample_reviews = [
        "정말 감명 깊게 읽은 책입니다. 추천합니다!",
        "스토리가 흥미진진하고 캐릭터들이 매력적이에요.",
        "글이 너무 어렵고 지루해서 중간에 포기했어요.",
        "이 책을 통해 많은 것을 배웠습니다. 다시 읽고 싶어요.",
        "작가의 문체가 독특하고 인상적이었어요.",
        "내용이 너무 진부하고 예상 가능했어요.",
    ]

    rows = []

    for u in DEMO_USERS:
        df = pd.read_sql(
            f"SELECT book_idx FROM my_book_progress_tb WHERE user_idx = {u}",
            engine,
        )

        book_list = df["book_idx"].tolist()  # 정수 리스트로 변환

        # 최근 2개만 리뷰 달아주기
        for b in book_list[:2]:
            rows.append(
                {
                    "user_idx": u,
                    "book_idx": int(b),
                    "content": random.choice(sample_reviews),
                    "created_at": random_datetime_within(10),
                }
            )

    # 루프 끝나고 한번만 insert
    if rows:
        pd.DataFrame(rows).to_sql(
            "book_review_tb", engine, if_exists="append", index=False
        )
        print("[OK] Demo BookReviews inserted.")


def seed_demo_friends(engine):
    print("[SEED] Demo Friend relationships...")

    rows = []

    rows.append(
        {
            "request_user_idx": 602,
            "receive_user_idx": 415,
            "status": "ACCEPTED",
            "created_at": datetime.utcnow(),
        }
    )
    rows.append(
        {
            "request_user_idx": 602,
            "receive_user_idx": 1278,
            "status": "ACCEPTED",
            "created_at": datetime.utcnow(),
        }
    )

    pd.DataFrame(rows).to_sql("friend_tb", engine, if_exists="append", index=False)


def seed_demo_messages(engine):
    print("[SEED] Demo Messages...")

    sample_messages = [
        "이 책 읽어봤어?",
        "추천해줘서 고마워!",
        "이 부분 진짜 좋더라",
        "나도 읽어볼게!",
    ]

    rows = []
    user_pairs = [(602, 415), (415, 1278), (602, 1278)]

    for sender, receiver in user_pairs:
        for _ in range(2):
            rows.append(
                {
                    "sender_idx": sender,
                    "receiver_idx": receiver,
                    "content": random.choice(sample_messages),
                    "is_read": random.random() < 0.5,
                    "sent_at": random_datetime_within(10),
                }
            )

    pd.DataFrame(rows).to_sql("message_tb", engine, if_exists="append", index=False)


def seed_demo_parties(engine):
    print("[SEED] Demo Reading Parties...")

    rows_party = []
    rows_member = []
    rows_progress = []

    popular_books = pd.read_sql(
        "SELECT idx FROM book_tb ORDER BY ratings_count DESC LIMIT 30", engine
    )["idx"].tolist()

    for u in DEMO_USERS:
        book_idx = int(random.choice(popular_books))

        party = {
            "host_user_idx": u,
            "book_idx": book_idx,
            "title": f"{u}님의 독서 파티",
            "description": "같이 읽어요!",
            "max_members": 10,
            "current_members": 1,
            "status": "OPEN",
            "is_private": False,
            "created_at": datetime.utcnow(),
        }
        rows_party.append(party)

    pd.DataFrame(rows_party).to_sql("party_tb", engine, if_exists="append", index=False)

    party_df = pd.read_sql(
        "SELECT idx, host_user_idx FROM party_tb ORDER BY idx DESC LIMIT 3", engine
    )

    for _, row in party_df.iterrows():
        pid = int(row["idx"])
        host = int(row["host_user_idx"])

        rows_member.append(
            {
                "party_idx": pid,
                "user_idx": host,
                "status": "ACTIVE",
            }
        )

        others = [u for u in DEMO_USERS if u != host]
        join_count = random.randint(1, 2)

        for j in random.sample(others, join_count):
            rows_member.append(
                {
                    "party_idx": pid,
                    "user_idx": j,
                    "status": "ACTIVE",
                }
            )

        for u in DEMO_USERS:
            rows_progress.append(
                {
                    "party_idx": pid,
                    "user_idx": u,
                    "progress": round(np.random.uniform(0.05, 0.6), 2),
                    "current_cfi_position": "/6/2[chapter1]!/4/12",
                    "updated_at": random_datetime_within(5),
                }
            )

    pd.DataFrame(rows_member).to_sql(
        "party_members_tb", engine, if_exists="append", index=False
    )
    pd.DataFrame(rows_progress).to_sql(
        "party_book_progress_tb", engine, if_exists="append", index=False
    )


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

    seed_demo_survey_ressponses(engine)
    seed_demo_recent_progress(engine)
    seed_reviews(engine)
    seed_demo_friends(engine)
    seed_demo_messages(engine)
    seed_demo_parties(engine)
    print("\n All Done! Database seeding completed successfully.\n")
