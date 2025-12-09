# ======================================================================
#  BookWheel SEED SCRIPT
# ======================================================================

from app.constants.constants import (
    SURVEY_GENRE_MAPPING,
    SURVEY_MOOD_MAPPING,
    SURVEY_PURPOSE_MAPPING,
)
import pandas as pd
from sqlalchemy import create_engine, text
import os, sys, random, bcrypt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import psycopg2

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

CSV_DIR = os.path.join(project_root, "dataset")
BOOKS_FILE = os.path.join(CSV_DIR, "books.csv")
RATINGS_FILE = os.path.join(CSV_DIR, "ratings.csv")
TAGS_FILE = os.path.join(CSV_DIR, "tags.csv")
BOOK_TAGS_FILE = os.path.join(CSV_DIR, "book_tags.csv")

DEMO_USERS = [41293, 50704, 32798]

# -------------------------------


def now():
    return datetime.now(timezone.utc)


def clean_isbn(val):
    if pd.isna(val):
        return None
    return str(val).replace(".0", "")[:13]


def rand_dt(days=7):
    delta = timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return datetime.now(timezone.utc) - delta


def hash_pw(pw):
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode()


from io import StringIO


from io import StringIO


def copy_from_df(table_name: str, df: pd.DataFrame, columns: list):
    col_str = ", ".join(columns)
    sql = f"""
        COPY {table_name} ({col_str})
        FROM STDIN
        WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
    """

    print(f"[COPY] Loading (memory) → {table_name}")

    buffer = StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.copy_expert(sql, buffer)
        raw_conn.commit()
    finally:
        raw_conn.close()


# ======================================================================
# RESET
# ======================================================================
def reset_database(engine):
    SQL = """
    TRUNCATE TABLE 
      book_comment_tb, book_highlight_tb, party_book_progress_tb,
      party_members_tb, party_tb, message_tb, friend_tb,
      book_review_tb, my_book_progress_tb, to_read_tb,
      book_rating_tb, book_tag_tb, survey_option_tag_tb,
      survey_option_tb, survey_question_tb, tag_tb,
      book_tb, user_basic_tb, user_social_tb, user_tb
    RESTART IDENTITY CASCADE;
    """
    with engine.connect() as conn:
        conn.execute(text(SQL))
        conn.commit()


def fix_user_sequence(engine):
    SQL = """SELECT setval(pg_get_serial_sequence('user_tb','idx'),
             (SELECT COALESCE(MAX(idx),1) FROM user_tb), true);"""
    with engine.connect() as conn:
        conn.execute(text(SQL))
        conn.commit()


# ======================================================================
# USER SEED
# ======================================================================
def seed_users(engine, max_user_idx):
    print("Seeding users...")

    AWS_REGION = os.getenv("AWS_REGION")
    AWS_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")

    if AWS_REGION is None or AWS_BUCKET is None:
        raise ValueError("AWS env not found")

    S3_BASE = f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com"

    normals = set(range(1, max_user_idx + 1)) - set(DEMO_USERS)

    normal_df = pd.DataFrame(
        {
            "idx": list(normals),
            "nickname": [f"user_{i}" for i in normals],
            "profile_image_path": [None] * len(normals),
            "type": ["BASIC"] * len(normals),
            "age": [random.randint(18, 40) for _ in normals],
            "gender": [random.choice(["M", "F"]) for _ in normals],
            "created_at": [now()] * len(normals),
            "deleted_at": [None] * len(normals),
        }
    )

    demo_df = pd.DataFrame(
        [
            {
                "idx": 41293,
                "nickname": "스릴러헌터",
                "profile_image_path": f"{S3_BASE}/user-profile/41293.jpeg",
                "type": "BASIC",
                "age": 29,
                "gender": "M",
                "created_at": now(),
                "deleted_at": None,
            },
            {
                "idx": 50704,
                "nickname": "드래곤마스터",
                "profile_image_path": f"{S3_BASE}/user-profile/50704.jpeg",
                "type": "BASIC",
                "age": 26,
                "gender": "F",
                "created_at": now(),
                "deleted_at": None,
            },
            {
                "idx": 32798,
                "nickname": "하트시럽",
                "profile_image_path": f"{S3_BASE}/user-profile/32798.jpg",
                "type": "BASIC",
                "age": 23,
                "gender": "F",
                "created_at": now(),
                "deleted_at": None,
            },
        ]
    )

    all_df = pd.concat([demo_df, normal_df], ignore_index=True)
    all_df.to_sql("user_tb", engine, if_exists="append", index=False)

    cred = pd.DataFrame(
        [
            {
                "user_idx": 41293,
                "id": "demo41293",
                "password": hash_pw("test1234!"),
                "email": "demo41293@bookwheel.com",
            },
            {
                "user_idx": 50704,
                "id": "demo50704",
                "password": hash_pw("test1234!"),
                "email": "demo50704@bookwheel.com",
            },
            {
                "user_idx": 32798,
                "id": "demo32798",
                "password": hash_pw("test1234!"),
                "email": "demo32798@bookwheel.com",
            },
        ]
    )
    cred.to_sql("user_basic_tb", engine, if_exists="append", index=False)


# ======================================================================
# BOOKS / TAGS / RATINGS
# ======================================================================
def seed_books(engine):
    print("Seeding books...")

    AWS_REGION = os.getenv("AWS_REGION")
    AWS_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")

    if AWS_REGION is None or AWS_BUCKET is None:
        raise ValueError("AWS env not found")

    S3_BASE = f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com"

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
            "isbn13": "isbn13",
        }
    )

    df["cover_image_path"] = df["idx"].apply(lambda x: f"{S3_BASE}/book-cover/{x}.jpg")

    df["publisher"] = df["publisher"].fillna("")
    df["description"] = df["description"].fillna("")
    df["language_code"] = df["language_code"].fillna("")
    df["isbn13"] = df["isbn13"].apply(clean_isbn)

    df["book_file_path"] = "/default/book.epub"

    df.loc[df["idx"] == 194, "book_file_path"] = (
        "https://s3.amazonaws.com/epubjs/books/moby-dick.epub"
    )

    df[
        [
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
    ].to_sql("book_tb", engine, if_exists="append", index=False, chunksize=4000)


def seed_tags(engine):
    print("Seeding tags...")
    df = pd.read_csv(TAGS_FILE)
    df = df.rename(columns={"Genre ID": "idx", "Genre Name": "name"})
    df.to_sql("tag_tb", engine, if_exists="append", index=False)


def seed_book_tags_copy():
    print("COPY book_tags from memory...")

    df = pd.read_csv(BOOK_TAGS_FILE)
    df = df.rename(columns={"book_id": "book_idx", "genre_id": "tag_idx"})

    # 메모리 COPY
    copy_from_df("book_tag_tb", df, ["book_idx", "tag_idx"])


def seed_ratings_copy():
    print("COPY ratings from memory...")

    df = pd.read_csv(RATINGS_FILE)
    df = df.rename(columns={"book_id": "book_idx", "user_id": "user_idx"})

    valid = set(pd.read_sql("SELECT idx FROM book_tb", engine)["idx"].tolist())
    df = df[df["book_idx"].isin(valid)]

    copy_from_df("book_rating_tb", df, ["user_idx", "book_idx", "rating"])


# ======================================================================
# SURVEY
# ======================================================================
survey_questions = [
    "주로 어떤 내용의 책에 손이 가시나요?",
    "책을 통해 어떤 기분을 느끼고 싶으신가요?",
    "책을 통해 주로 무엇을 얻고 싶으신가요?",
    "최근에 감명 깊게 읽은 책은 무엇인가요?",
]

survey_options_list = [
    list(SURVEY_GENRE_MAPPING.keys()),
    list(SURVEY_MOOD_MAPPING.keys()),
    list(SURVEY_PURPOSE_MAPPING.keys()),
    [2, 9, 4, 10, 15, 374],
]


def seed_survey_questions(engine):
    print("Seeding survey questions...")
    pd.DataFrame({"content": survey_questions}).to_sql(
        "survey_question_tb", engine, if_exists="append", index=False
    )


def seed_survey_options(engine):
    print("Seeding survey options...")
    qids = pd.read_sql("SELECT idx FROM survey_question_tb ORDER BY idx", engine)[
        "idx"
    ].tolist()
    rows = []
    for i, opts in enumerate(survey_options_list):
        qid = qids[i]
        if i == 3:
            for b in opts:
                rows.append({"question_idx": qid, "book_idx": b})
        else:
            for o in opts:
                rows.append({"question_idx": qid, "content": o})
    pd.DataFrame(rows).to_sql(
        "survey_option_tb", engine, if_exists="append", index=False
    )


def seed_survey_option_tags(engine):
    print("Seeding survey option tags...")
    tags = pd.read_sql("SELECT idx,name FROM tag_tb", engine)
    opt = pd.read_sql(
        "SELECT idx,question_idx,content FROM survey_option_tb WHERE content IS NOT NULL",
        engine,
    )
    tag_map = {n.lower(): i for i, n in zip(tags["idx"], tags["name"])}

    ALL = {**SURVEY_GENRE_MAPPING, **SURVEY_MOOD_MAPPING, **SURVEY_PURPOSE_MAPPING}
    rows = []
    for _, row in opt.iterrows():
        c = row["content"]
        if c in ALL:
            for t in ALL[c]:
                tid = tag_map.get(t.lower())
                if tid:
                    rows.append({"option_idx": row["idx"], "tag_idx": tid})

    pd.DataFrame(rows).to_sql(
        "survey_option_tag_tb", engine, if_exists="append", index=False
    )


def seed_demo_survey_responses(engine):
    print("Seeding demo survey responses...")
    q1, q2, q3, _ = pd.read_sql(
        "SELECT idx FROM survey_question_tb ORDER BY idx", engine
    )["idx"].tolist()
    opt_df = pd.read_sql(
        "SELECT idx,question_idx,content FROM survey_option_tb", engine
    )

    def get_opt(qid, content):
        return int(
            opt_df[(opt_df["question_idx"] == qid) & (opt_df["content"] == content)][
                "idx"
            ].iloc[0]
        )

    DEMO_GENRE = {41293: "미스터리/스릴러", 50704: "판타지", 32798: "로맨스"}
    DEMO_MOOD = {
        41293: "#긴장감_넘치는",
        50704: "#유쾌하고_재미있는",
        32798: "#가슴_따뜻한",
    }
    DEMO_PURPOSE = {
        41293: "재미와 교양 쌓기",
        50704: "스트레스 해소",
        32798: "따뜻한 위로와 감동",
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
# DEMO ACTIVITY
# ======================================================================
GENRE_MAP = {
    "미스터리/스릴러": ["mystery", "thriller", "suspense", "crime"],
    "판타지": ["fantasy", "epic", "magic"],
    "로맨스": ["romance", "love", "chick lit"],
}


def seed_my_progress_custom(engine):
    print("Seeding MY CUSTOM progress...")

    BOOKS = [1534, 1934, 2964, 26]

    rows = []
    for i, b in enumerate(BOOKS):
        rows.append(
            {
                "user_idx": 41293,
                "book_idx": int(b),
                "progress": round(random.uniform(0.4, 0.98), 3),
                "current_cfi_position": f"/6/2[{i}]!/4/{i}",
                "updated_at": now() + timedelta(minutes=i),
            }
        )

    rows[3]["updated_at"] = now() + timedelta(hours=2)

    pd.DataFrame(rows).to_sql(
        "my_book_progress_tb", engine, if_exists="append", index=False
    )


def seed_custom_parties(engine):
    print("Seeding CUSTOM parties...")
    MOBY = 194
    CATCHER = 8
    PRIDE = 10

    party_rows = [
        {
            "host_user_idx": 41293,
            "book_idx": MOBY,
            "title": "고전 명작 ‘모비딕’ 깊이 읽기",
            "description": "끝없는 집착과 광기의 항해를 함께 따라가요. 고전이지만 쉽고 재미있게 읽는 모임입니다.",
            "max_members": 10,
            "current_members": 3,
            "status": "OPEN",
            "is_private": False,
            "created_at": now(),
        },
        {
            "host_user_idx": 50704,
            "book_idx": CATCHER,
            "title": "더 캐처 인 더 라이 감성 토크",
            "description": "홀든의 감정을 따라가며 각자 공감한 장면을 나누는 모임입니다.",
            "max_members": 10,
            "current_members": 3,
            "status": "OPEN",
            "is_private": False,
            "created_at": now(),
        },
        {
            "host_user_idx": 32798,
            "book_idx": PRIDE,
            "title": "오만과 편견 명대사 함께 읽기",
            "description": "엘리자베스와 다아시의 감정 변화를 이야기하는 따뜻한 분위기의 모임입니다.",
            "max_members": 10,
            "current_members": 3,
            "status": "OPEN",
            "is_private": False,
            "created_at": now(),
        },
    ]

    pd.DataFrame(party_rows).to_sql("party_tb", engine, if_exists="append", index=False)

    party_df = pd.read_sql("SELECT idx FROM party_tb ORDER BY idx DESC LIMIT 3", engine)

    MEMBERS = [41293, 50704, 32798]
    member_rows = []
    progress_rows = []

    for _, row in party_df.iterrows():
        pid = int(row["idx"])

        for i, u in enumerate(MEMBERS):
            member_rows.append({"party_idx": pid, "user_idx": u, "status": "JOINED"})
            progress_rows.append(
                {
                    "party_idx": pid,
                    "user_idx": u,
                    "progress": round(random.uniform(0.1, 0.9), 2),
                    "current_cfi_position": "/6/2[last]!/4/12",
                    "updated_at": now() + timedelta(minutes=i),
                }
            )

    pd.DataFrame(member_rows).to_sql(
        "party_members_tb", engine, if_exists="append", index=False
    )
    pd.DataFrame(progress_rows).to_sql(
        "party_book_progress_tb", engine, if_exists="append", index=False
    )


def seed_reviews(engine):
    print("Seeding book reviews...")
    samples = [
        "정말 재미있었어요!",
        "몰입감 최고!",
        "조금 아쉬웠습니다.",
        "감동적이었어요.",
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
                    "content": random.choice(samples),
                    "created_at": rand_dt(5),
                }
            )
    pd.DataFrame(rows).to_sql("book_review_tb", engine, if_exists="append", index=False)


def seed_demo_friends(engine):
    print("Seeding demo friends...")
    rows = [
        {
            "request_user_idx": 41293,
            "receive_user_idx": 50704,
            "status": "ACCEPTED",
            "created_at": now(),
        },
        {
            "request_user_idx": 50704,
            "receive_user_idx": 32798,
            "status": "ACCEPTED",
            "created_at": now(),
        },
    ]
    pd.DataFrame(rows).to_sql("friend_tb", engine, if_exists="append", index=False)


def seed_demo_messages(engine):
    print("Seeding demo messages...")
    msgs = ["이 책 봤어?", "완전 재밌음!", "추천해줘!", "읽어볼게!"]
    pairs = [(41293, 50704), (50704, 32798), (41293, 32798)]
    rows = []
    for s, r in pairs:
        for _ in range(2):
            rows.append(
                {
                    "sender_idx": s,
                    "receiver_idx": r,
                    "content": random.choice(msgs),
                    "is_read": random.random() < 0.5,
                    "sent_at": rand_dt(10),
                }
            )
    pd.DataFrame(rows).to_sql("message_tb", engine, if_exists="append", index=False)


def seed_demo_highlights(engine):
    print("Seeding demo highlights...")

    rows = [
        {
            "party_idx": 1,
            "user_idx": 41293,
            "book_idx": 12,
            "cfi_range": "epubcfi(/6/8!/4/2/4,:1:15,/1:26)",
            "content": "combination",
            "color_code": "#FFA07A",
            "created_at": now(),
            "deleted_at": None,
        },
        {
            "party_idx": 1,
            "user_idx": 41293,
            "book_idx": 12,
            "cfi_range": "epubcfi(/6/8!/4/2/4,:1:224,/1:234)",
            "content": "preserving",
            "color_code": "#FFA07A",
            "created_at": now(),
            "deleted_at": None,
        },
    ]

    pd.DataFrame(rows).to_sql(
        "book_highlight_tb", engine, if_exists="append", index=False
    )


def seed_demo_comments(engine):
    print("Seeding demo comments...")

    rows = [
        {
            "user_idx": 41293,
            "book_idx": 12,
            "highlight_idx": 1,
            "content": "이 문단이 정말 핵심을 잘 짚어주는 것 같아요.",
            "created_at": now(),
        }
    ]

    pd.DataFrame(rows).to_sql(
        "book_comment_tb", engine, if_exists="append", index=False
    )


# ======================================================================
# MAIN
# ======================================================================
if __name__ == "__main__":
    reset_database(engine)

    try:
        max_uid = pd.read_csv(RATINGS_FILE)["user_id"].max()
    except:
        max_uid = 500

    seed_users(engine, max_uid)
    fix_user_sequence(engine)

    seed_books(engine)
    seed_tags(engine)
    seed_book_tags_copy()
    seed_ratings_copy()

    seed_survey_questions(engine)
    seed_survey_options(engine)
    seed_survey_option_tags(engine)
    seed_demo_survey_responses(engine)

    seed_reviews(engine)
    seed_demo_friends(engine)
    seed_demo_messages(engine)
    seed_custom_parties(engine)
    seed_my_progress_custom(engine)

    seed_demo_highlights(engine)
    seed_demo_comments(engine)

    print("All Done!")
