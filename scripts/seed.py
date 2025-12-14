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
from io import StringIO


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

DEMO_USERS = {
    41293,
    50704,
    32798,
}

FRIEND_USERS = {
    120,
    341,
    782,
    1450,
    2333,
    12,
    5,
    3,
}

FRIEND_REQUEST_USER = {
    11,
    893,
    2048,
}

RECOMMEND_USERS = {
    5797,
    24071,
    30424,
    32427,
    33047,
    46494,
    48046,
    48314,
    52895,
    53393,
}

USER_SEED_META = {
    # -----------------------------
    # DEMO USERS
    # -----------------------------
    41293: {"nickname": "스릴러헌터", "gender": "M", "age": 29},
    50704: {"nickname": "드래곤마스터", "gender": "F", "age": 26},
    32798: {"nickname": "하트시럽", "gender": "F", "age": 23},
    # -----------------------------
    # FRIEND USERS
    # -----------------------------
    120: {"nickname": "심야독서가", "gender": "M", "age": 34},
    341: {"nickname": "문장수집가", "gender": "M", "age": 29},
    782: {"nickname": "블랙페이지", "gender": "F", "age": 31},
    1450: {"nickname": "사건의독자", "gender": "F", "age": 27},
    2333: {"nickname": "트리거", "gender": "M", "age": 36},
    12: {"nickname": "온기페이지", "gender": "F", "age": 24},
    5: {"nickname": "사유의숲", "gender": "M", "age": 38},
    3: {"nickname": "가벼운책상", "gender": "M", "age": 21},
    # -----------------------------
    # FRIEND REQUEST USERS
    # -----------------------------
    11: {"nickname": "비밀독서가", "gender": "F", "age": 28},
    893: {"nickname": "책속탐정", "gender": "M", "age": 35},
    2048: {"nickname": "페이지워커", "gender": "F", "age": 30},
    # -----------------------------
    # RECOMMEND USERS
    # -----------------------------
    5797: {"nickname": "단서추적자", "gender": "M", "age": 33},
    24071: {"nickname": "침묵의독자", "gender": "M", "age": 36},
    30424: {"nickname": "검은서가", "gender": "M", "age": 27},
    32427: {"nickname": "의문의페이지", "gender": "M", "age": 30},
    33047: {"nickname": "심야서재", "gender": "M", "age": 28},
    46494: {"nickname": "사건기록자", "gender": "M", "age": 36},
    48046: {"nickname": "추리광", "gender": "M", "age": 32},
    48314: {"nickname": "검은문장", "gender": "M", "age": 22},
    52895: {"nickname": "미궁독서가", "gender": "M", "age": 24},
    53393: {"nickname": "복선수집가", "gender": "M", "age": 36},
}
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


def rand_dt_range(min_days: int, max_days: int):
    return datetime.now(timezone.utc) - timedelta(
        days=random.randint(min_days, max_days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


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

    SEED_USER_IDXLIST = (
        DEMO_USERS | FRIEND_USERS | FRIEND_REQUEST_USER | RECOMMEND_USERS
    )

    rows = []
    for uidx in SEED_USER_IDXLIST:
        meta = USER_SEED_META[uidx]
        rows.append(
            {
                "idx": uidx,
                "nickname": meta["nickname"],
                "profile_image_path": f"{S3_BASE}/user-profile/{uidx}.jpg",
                "type": "BASIC",
                "age": meta["age"],
                "gender": meta["gender"],
                "created_at": now(),
            }
        )
    user_df = pd.DataFrame(rows)

    normals = set(range(1, max_user_idx + 1)) - SEED_USER_IDXLIST

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

    all_df = pd.concat([user_df, normal_df], ignore_index=True)
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
    df["average_rating"] = pd.to_numeric(df["average_rating"], errors="coerce")
    df["average_rating"] = df["average_rating"].fillna(0.0)

    df["book_file_path"] = "/default/book.epub"

    PARTY_BOOK_IDXS = {
        1,
        2,
        3,
        10,
        15,
        29,
        34,
        46,
        47,
        50,
        194,
        209,
        30,
        244,
        446,
    }

    MOBY_EPUB = "https://s3.amazonaws.com/epubjs/books/moby-dick.epub"

    df["book_file_path"] = "/default/book.epub"

    df.loc[df["idx"].isin(PARTY_BOOK_IDXS), "book_file_path"] = MOBY_EPUB

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
    print("Seeding ALL survey responses...")

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

    # ---------------- DEMO ----------------
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

    # ---------------- FRIEND ----------------
    FRIEND_GENRE = {
        120: "미스터리/스릴러",
        341: "인문/교양",
        782: "로맨스",
        1450: "미스터리/스릴러",
        2333: "판타지",
        12: "미스터리/스릴러",
        5: "미스터리/스릴러",
        3: "소설",
    }
    FRIEND_MOOD = {
        120: "#긴장감_넘치는",
        341: "#지적_호기심이_채워지는",
        782: "#가슴_따뜻한",
        1450: "#긴장감_넘치는",
        2333: "#힐링되는",
        12: "#긴장감_넘치는",
        5: "#생각이_깊어지는",
        3: "#가볍게_읽는",
    }
    FRIEND_PURPOSE = {
        120: "재미와 교양 쌓기",
        341: "새로운 관점과 아이디어 얻기",
        782: "따뜻한 위로와 감동",
        1450: "재미와 교양 쌓기",
        2333: "스트레스 해소",
        12: "스트레스 해소",
        5: "새로운 관점과 아이디어 얻기",
        3: "편안한 휴식",
    }

    # ---------------- FRIEND REQUEST ----------------
    FREIND_REQUEST_GNERE = {
        11: "미스터리/스릴러",
        893: "미스터리/스릴러",
        2048: "소설",
    }
    FREIND_REQUEST_MOOD = {
        11: "#긴장감_넘치는",
        893: "#긴장감_넘치는",
        2048: "#가볍게_읽는",
    }
    FREIND_REQUEST_PURPOSE = {
        11: "스트레스 해소",
        893: "재미와 교양 쌓기",
        2048: "편안한 휴식",
    }

    # ---------------- RECOMMEND ----------------
    RECOMMEND_GENRE = {u: "미스터리/스릴러" for u in RECOMMEND_USERS}
    RECOMMEND_MOOD = {
        5797: "#긴장감_넘치는",
        24071: "#생각이_깊어지는",
        30424: "#긴장감_넘치는",
        32427: "#생각이_깊어지는",
        33047: "#긴장감_넘치는",
        46494: "#생각이_깊어지는",
        48046: "#긴장감_넘치는",
        48314: "#긴장감_넘치는",
        52895: "#생각이_깊어지는",
        53393: "#생각이_깊어지는",
    }
    RECOMMEND_PURPOSE = {
        5797: "재미와 교양 쌓기",
        24071: "새로운 관점과 아이디어 얻기",
        30424: "재미와 교양 쌓기",
        32427: "새로운 관점과 아이디어 얻기",
        33047: "재미와 교양 쌓기",
        46494: "새로운 관점과 아이디어 얻기",
        48046: "재미와 교양 쌓기",
        48314: "재미와 교양 쌓기",
        52895: "새로운 관점과 아이디어 얻기",
        53393: "새로운 관점과 아이디어 얻기",
    }

    rows = []

    def add_user(u, g, m, p):
        rows.extend(
            [
                {"user_idx": u, "option_idx": get_opt(q1, g)},
                {"user_idx": u, "option_idx": get_opt(q2, m)},
                {"user_idx": u, "option_idx": get_opt(q3, p)},
            ]
        )

    for u in DEMO_USERS:
        add_user(u, DEMO_GENRE[u], DEMO_MOOD[u], DEMO_PURPOSE[u])

    for u in FRIEND_USERS:
        add_user(u, FRIEND_GENRE[u], FRIEND_MOOD[u], FRIEND_PURPOSE[u])

    for u in FRIEND_REQUEST_USER:
        add_user(
            u,
            FREIND_REQUEST_GNERE[u],
            FREIND_REQUEST_MOOD[u],
            FREIND_REQUEST_PURPOSE[u],
        )
    for u in RECOMMEND_USERS:
        add_user(u, RECOMMEND_GENRE[u], RECOMMEND_MOOD[u], RECOMMEND_PURPOSE[u])

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
    SILENCE = 209
    GONE = 30
    SHARP = 244
    SHERLOCK = 446

    party_rows = [
        {
            "host_user_idx": 41293,
            "book_idx": MOBY,
            "title": "고전 명작 ‘모비딕’ 깊이 읽기",
            "description": "끝없는 집착과 광기의 항해를 함께 따라가요.",
            "max_members": 10,
            "current_members": 3,
            "status": "OPEN",
            "is_private": True,
            "created_at": rand_dt_range(1, 2),
        },
        {
            "host_user_idx": 1450,
            "book_idx": SILENCE,
            "title": "『양들의 침묵』 심리 스릴러 토론",
            "description": "한니발 렉터의 심리를 파헤쳐봅니다.",
            "max_members": 3,
            "current_members": 3,
            "status": "FULL",
            "is_private": False,
            "created_at": rand_dt_range(6, 10),
        },
        {
            "host_user_idx": 11,
            "book_idx": GONE,
            "title": "『나를 찾아줘』 반전 분석 모임",
            "description": "후반부 반전을 중심으로 토론합니다.",
            "max_members": 3,
            "current_members": 3,
            "status": "FULL",
            "is_private": False,
            "created_at": rand_dt_range(5, 9),
        },
        {
            "host_user_idx": 12,
            "book_idx": SHARP,
            "title": "어두운 심리 속으로 빠져 보아요",
            "description": "트라우마 및 폭력 주의",
            "max_members": 3,
            "current_members": 3,
            "status": "FULL",
            "is_private": False,
            "created_at": rand_dt_range(4, 8),
        },
        {
            "host_user_idx": 120,
            "book_idx": SHERLOCK,
            "title": "셜록 홈즈 미스터리 읽기",
            "description": "레전드 추리 소설 같이 읽어요",
            "max_members": 5,
            "current_members": 5,
            "status": "FULL",
            "is_private": False,
            "created_at": rand_dt_range(3, 7),
        },
    ]

    pd.DataFrame(party_rows).to_sql("party_tb", engine, if_exists="append", index=False)

    party_df = pd.read_sql(
        """
        SELECT idx, book_idx
        FROM party_tb
        WHERE book_idx IN (194, 209, 30, 244, 446)
        """,
        engine,
    )

    PARTY_MEMBERS = {
        MOBY: [41293, 50704, 32798],
        SILENCE: [1450, 48314, 41293],
        GONE: [11, 41293, 120],
        SHARP: [12, 41293, 3],
        SHERLOCK: [120, 50704, 5797, 2048, 41293],
    }

    member_rows = []
    progress_rows = []

    for _, row in party_df.iterrows():
        pid = int(row["idx"])
        book_idx = int(row["book_idx"])

        members = PARTY_MEMBERS.get(book_idx, [])

        for u in members:
            member_rows.append(
                {
                    "party_idx": pid,
                    "user_idx": u,
                    "status": "JOINED",
                }
            )

            progress_rows.append(
                {
                    "party_idx": pid,
                    "user_idx": u,
                    "progress": round(random.uniform(0.3, 0.95), 2),
                    "current_cfi_position": "/6/2[last]!/4/12",
                    "updated_at": rand_dt_range(0, 3),
                }
            )

    pd.DataFrame(member_rows).to_sql(
        "party_members_tb", engine, if_exists="append", index=False
    )

    pd.DataFrame(progress_rows).to_sql(
        "party_book_progress_tb", engine, if_exists="append", index=False
    )


def seed_open_parties(engine):
    print("Seeding OPEN parties...")

    OPEN_PARTY_BOOKS = [
        (1, "레전드 명작 헝거게임 같이 읽기", "디스토피아 세계에서 살아남아봐요."),
        (2, "해리포터 원작 읽어 봐야지!", "영화로만 알던 마법 세계를 소설로 즐겨봐요."),
        (3, "설레는 뱀파이어 볼 사람", "심쿵 주의!!"),
        (10, "오만과 편견 같이 읽기", "고전 로맨스를 즐겨요."),
        (15, "안네의 일기 읽으며 토론해요", "한 소녀의 생각을 함께 나눕니다."),
        (
            29,
            "현대 사회에 필요한 사랑 이야기, 로미오와 줄리엣",
            "이루어질 수 없는 사랑",
        ),
        (
            34,
            "아찔한 사랑 이야기 몰래 읽으실 분",
            "비밀스럽고 위험한 사랑이야기 가볍게 즐겨요.",
        ),
        (46, "서커스 속 사랑과 생존 이야기", "인간의 사랑과 생존에 대해"),
        (
            47,
            "죽음이 들려주는 사랑 이야기 함께 읽기",
            "삶과 죽음, 그리고 사랑에 대하여",
        ),
        (50, "상상력 산책", "유머와 상상력 붐!"),
    ]

    hosts = list(
        (DEMO_USERS | FRIEND_REQUEST_USER | FRIEND_USERS | RECOMMEND_USERS) - {41923}
    )

    party_rows = []

    for book_idx, title, description in OPEN_PARTY_BOOKS:
        host = random.choice(hosts)
        max_m = random.randint(4, 8)
        cur_m = random.randint(1, max_m - 1)

        party_rows.append(
            {
                "host_user_idx": host,
                "book_idx": book_idx,
                "title": title,
                "description": description,
                "max_members": max_m,
                "current_members": cur_m,
                "status": "OPEN",
                "is_private": False,
                "created_at": rand_dt_range(0, 5),
            }
        )

    pd.DataFrame(party_rows).to_sql("party_tb", engine, if_exists="append", index=False)

    party_df = pd.read_sql(
        """
        SELECT idx, host_user_idx
        FROM party_tb
        WHERE is_private = FALSE
          AND status = 'OPEN'
        ORDER BY idx DESC
        LIMIT %s
        """
        % len(OPEN_PARTY_BOOKS),
        engine,
    )

    for _, row in party_df.iterrows():
        pidx = int(row["idx"])
        host = int(row["host_user_idx"])

        member_rows = [
            {
                "party_idx": pidx,
                "user_idx": host,
                "status": "JOINED",
            }
        ]

        others = list((FRIEND_USERS | RECOMMEND_USERS) - {host, 41293})
        random.shuffle(others)

        for u in others[: random.randint(0, 2)]:
            member_rows.append(
                {
                    "party_idx": pidx,
                    "user_idx": u,
                    "status": "JOINED",
                }
            )

        pd.DataFrame(member_rows).to_sql(
            "party_members_tb", engine, if_exists="append", index=False
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
    rows = []
    for demo_uidx in DEMO_USERS:
        for friend_uidx in FRIEND_USERS:
            rows.append(
                {
                    "request_user_idx": demo_uidx,
                    "receive_user_idx": friend_uidx,
                    "status": "ACCEPTED",
                    "created_at": now(),
                }
            )

    pd.DataFrame(rows).to_sql("friend_tb", engine, if_exists="append", index=False)


def seed_demo_friend_requests(engine):
    print("Seeding demo friend requests (PENDING)...")

    rows = [
        {
            "request_user_idx": 11,
            "receive_user_idx": 41293,
            "status": "PENDING",
            "created_at": now() - timedelta(hours=2),
        },
        {
            "request_user_idx": 893,
            "receive_user_idx": 41293,
            "status": "PENDING",
            "created_at": now() - timedelta(hours=5),
        },
        {
            "request_user_idx": 2048,
            "receive_user_idx": 41293,
            "status": "PENDING",
            "created_at": now() - timedelta(days=1),
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
    seed_demo_friend_requests(engine)
    seed_demo_messages(engine)
    seed_custom_parties(engine)
    seed_open_parties(engine)
    seed_my_progress_custom(engine)

    seed_demo_highlights(engine)
    seed_demo_comments(engine)

    print("All Done!")
