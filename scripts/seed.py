import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# --- 환경 설정 ---
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "[ERROR] DATABASE_URL is not set in environment variables.")

engine = create_engine(DATABASE_URL)

# --- 파일 경로 설정 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
CSV_DIR = os.path.join(project_root, "goodbooks-10k")

RATINGS_FILE = os.path.join(CSV_DIR, "ratings.csv")
BOOKS_FILE = os.path.join(CSV_DIR, "books.csv")
TAGS_FILE = os.path.join(CSV_DIR, "tags.csv")
BOOK_TAGS_FILE = os.path.join(CSV_DIR, "book_tags.csv")


# ===========================================================================
# 설문조사 매핑 데이터
# ===========================================================================

SURVEY_GENRE_MAPPING = {
    "소설": ["Fiction", "Literary Fiction", "Realistic Fiction", "Adult Fiction", "Contemporary", "Womens Fiction", "Novels", "Literature", "Drama"],
    "고전": ["Classics", "Classic Literature", "Literature", "British Literature", "American Literature", "School", "Read For School", "Modern Classics"],
    "미스터리 / 스릴러": ["Mystery", "Thriller", "Mystery Thriller", "Murder Mystery", "Psychological Thriller", "Legal Thriller", "Spy Thriller", "Crime", "Suspense", "Detective", "Horror"],
    "판타지": ["Fantasy", "High Fantasy", "Epic Fantasy", "Urban Fantasy", "Magic", "Paranormal", "Supernatural", "Vampires", "Witches", "Fae", "Fairy Tales"],
    "SF": ["Science Fiction", "Dystopia", "Space", "Time Travel", "Aliens", "Steampunk", "Cyberpunk", "Hard Science Fiction"],
    "로맨스": ["Romance", "Contemporary Romance", "Historical Romance", "Paranormal Romance", "Regency Romance", "Sports Romance", "Love", "Chick Lit", "Romantic Suspense"],
    "역사": ["Historical", "Historical Fiction", "History", "War", "World War II", "19th Century", "20th Century", "American History", "Alternative History"],
    "청소년": ["Young Adult", "Young Adult Fantasy", "Young Adult Contemporary", "Young Adult Romance", "Childrens", "Midldle Grade", "Teen", "Coming of Age"],
    "인물 / 회고록": ["Biography", "Biography Memoir", "Memoir", "Autobiography"],
    "자기계발": ["Self Help", "Psychology", "Business", "Leadership", "Personal Development", "Inspirational", "Spirituality", "Productivity"],
    "논픽션": ["Nonfiction", "Essays", "Philosophy", "Science", "Politics", "Popular Science", "Travel", "Social Science", "Humanities", "Neuroscience"]
}

SURVEY_MOOD_MAPPING = {
    "#힐링되는": ["Inspirational", "Spirituality", "Self Help", "Faith"],
    "#긴장감_넘치는": ["Suspense", "Thriller", "Mystery", "Crime", "Mystery Thriller", "Murder Mystery", "Horror", "Dark"],
    "#가슴_따뜻한": ["Family", "Love", "Romance", "Contemporary Romance", "Relationships"],
    "#지적_호기심이_채워지는": ["Nonfiction", "History", "Science", "Philosophy", "Politics", "Economics", "Psychology", "Business"],
    "#생각이_깊어지는": ["Philosophy", "Psychology", "Classics", "Literary Fiction", "Literature", "Spirituality"],
    "#가볍게_읽는": ["Chick Lit", "Humor", "Comics", "Graphic Novels", "Manga", "Young Adult", "Romance"],
    "#유쾌하고_재미있는": ["Humor", "Comics", "Comedy", "Chick Lit"],
    "#눈물_나는": ["Drama", "Historical Fiction", "War", "Memoir", "Tragedy"]
}

SURVEY_PURPOSE_MAPPING = {
    "재미와 교양 쌓기": ["Fiction", "Novels", "Literature", "Classics", "Historical Fiction", "Nonfiction"],
    "스트레스 해소": ["Fantasy", "Science Fiction", "Comics", "Graphic Novels", "Comedy", "Humor", "Manga", "Young Adult"],
    "따뜻한 위로와 감동": ["Inspirational", "Spirituality", "Memoir", "Biography", "Faith", "Poetry", "Essays"],
    "커리어 역량 향상": ["Business", "Leadership", "Management", "Economics", "Fianance", "Money", "Entrepreneurship"],
    "편안한 휴식": ["Chick Lit", "Romance", "Humor", "Cookbooks", "Travel", "Poetry"],
    "새로운 관점과 아이디어 얻기": ["Philosophy", "Psychology", "Science", "Politics", "Social Science", "Essays", "History", "Nonfiction"]
}

# 질문 및 옵션 리스트 생성
survey_questions = [
    "주로 어떤 내용의 책에 손이 가시나요?",
    "책을 통해 어떤 기분을 느끼고 싶으신가요?",
    "책을 통해 주로 무엇을 얻고 싶으신가요?"
]

survey_options_list = [
    list(SURVEY_GENRE_MAPPING.keys()),
    list(SURVEY_MOOD_MAPPING.keys()),
    list(SURVEY_PURPOSE_MAPPING.keys())
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
    users = pd.DataFrame({
        "nickname": [f"user_{i}" for i in range(1, user_count + 1)]
    })
    users.to_sql("user_tb", engine, if_exists="append",
                 index=False, chunksize=5000)


def seed_books(engine):
    print("[INFO] Seeding books...")
    if not os.path.exists(BOOKS_FILE):
        print(f"[ERROR] File not found: {BOOKS_FILE}")
        return

    df = pd.read_csv(BOOKS_FILE)
    df = df.rename(columns={
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
    })

    # 결측치 및 데이터 정제
    df["publisher"] = df["publisher"].fillna("")
    df["description"] = df["description"].fillna("")
    df["language_code"] = df["language_code"].fillna("")
    df["book_file_path"] = "/default/path/book.epub"
    df["isbn13"] = df["isbn13"].apply(clean_isbn)

    # ISBN 빈값 처리
    df.loc[df["isbn13"] == "", "isbn13"] = None

    cols = [
        "idx", "title", "author", "publisher", "publication_year",
        "description", "book_file_path", "cover_image_path",
        "average_rating", "ratings_count", "language_code", "isbn13"
    ]
    df[cols].to_sql("book_tb", engine, if_exists="append",
                    index=False, chunksize=10000)


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
        "book_tag_tb", engine, if_exists="append", index=False, chunksize=10000)


def seed_ratings(engine):
    print("[INFO] Seeding ratings...")
    df = pd.read_csv(RATINGS_FILE)
    df = df.rename(columns={"user_id": "user_idx",
                   "book_id": "book_idx", "rating": "rating"})

    # 유효한 책 ID만 필터링
    valid_books = pd.read_sql("SELECT idx FROM book_tb", engine)[
        "idx"].tolist()
    valid_books_set = set(valid_books)
    df = df[df["book_idx"].isin(valid_books_set)]

    df[["user_idx", "book_idx", "rating"]].to_sql(
        "book_rating_tb", engine, if_exists="append", index=False, chunksize=20000)


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
        "SELECT idx, content FROM survey_question_tb ORDER BY idx", engine)

    if df_q.empty:
        print("[ERROR] No questions found! Skipping options.")
        return

    insert_rows = []
    for i, options in enumerate(survey_options_list):
        if i >= len(df_q):
            break
        qid = int(df_q.iloc[i]["idx"])

        for opt in options:
            insert_rows.append({"question_idx": qid, "content": opt})

    df = pd.DataFrame(insert_rows)
    df.to_sql("survey_option_tb", engine, if_exists="append", index=False)


def seed_survey_option_tags(engine):
    print("[INFO] Seeding survey option-tag mappings...")

    tags_df = pd.read_sql("SELECT idx, name FROM tag_tb", engine)
    tag_map = {name.lower(): idx for idx, name in zip(
        tags_df["idx"], tags_df["name"])}

    options_df = pd.read_sql(
        "SELECT idx, content FROM survey_option_tb", engine)

    ALL_MAPPINGS = {**SURVEY_GENRE_MAPPING, **
                    SURVEY_MOOD_MAPPING, **SURVEY_PURPOSE_MAPPING}

    insert_rows = []
    for _, row in options_df.iterrows():
        option_id = row["idx"]
        option_text = row["content"]
        target_tags = ALL_MAPPINGS.get(option_text, [])

        for tag_name in target_tags:
            tag_id = tag_map.get(tag_name.lower())
            if tag_id:
                insert_rows.append(
                    {"option_idx": option_id, "tag_idx": tag_id})

    if not insert_rows:
        print("[WARN] No mappings to insert!")
        return

    df = pd.DataFrame(insert_rows)
    df.to_sql("survey_option_tag_tb", engine, if_exists="append", index=False)


# ===========================================================================
# 3. 메인 실행 (초기화 및 시딩)
# ===========================================================================
if __name__ == "__main__":

    # 파일 체크
    for f in [BOOKS_FILE, TAGS_FILE, BOOK_TAGS_FILE, RATINGS_FILE]:
        if not os.path.exists(f):
            print(f"[ERROR] Missing file: {f}")
            exit()

    print("\n Starting Database Reset & Seed...\n")

    try:
        max_user_idx = pd.read_csv(RATINGS_FILE)["user_id"].max()
    except:
        max_user_idx = 100

    seed_fake_users(engine, max_user_idx)
    seed_books(engine)
    seed_tags(engine)
    seed_book_tags(engine)
    seed_ratings(engine)

    seed_survey_questions(engine)
    seed_survey_options(engine)
    seed_survey_option_tags(engine)

    print("\n All Done! Database seeding completed successfully.\n")
