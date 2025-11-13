import pandas as pd
from sqlalchemy import create_engine, text
import os
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# --- (1) DB 접속 설정 ---
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_NAME = os.environ.get("DB_NAME")

# .env 파일에 값이 하나라도 없으면 에러 발생
if not all([DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME]):
    print("Error: Missing one or more database environment variables.")
    exit()

# SQLAlchemy 접속 문자열
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- (2) CSV 파일 경로 ---
CSV_DIR = "goodbooks-10k"

RATINGS_FILE = os.path.join(CSV_DIR, "ratings.csv")
BOOKS_FILE = os.path.join(CSV_DIR, "books.csv")
TAGS_FILE  = os.path.join(CSV_DIR, "tags.csv")
BOOK_TAGS_FILE = os.path.join(CSV_DIR, "book_tags.csv")

# --- (3) Fake users 생성 (ratings의 user_id 기준) ---
def seed_fake_users(engine, user_count: int):
    print(f"Seeding {user_count} fake users into user_tb...")
    users = pd.DataFrame({
        "nickname": [f"user_{i}" for i in range(1, user_count + 1)]
    })
    users.to_sql("user_tb", engine, if_exists="append", index=False, chunksize=5000)
    print(f"Inserted {len(users)} users.")
    
# --- (4) isbn 정제 ---
def clean_isbn(val) :
    if pd.isna(val) :
        return ""
    s = str(val).strip()
    s = s.replace(".0", "")
    s = s[:13]
    return s

# --- (5) Books 삽입 ---
def seed_books(engine):
    print("Seeding book_tb ...")
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
    
   # 빈 값 채우기
    df["publisher"] = df["publisher"].fillna("")
    df["description"] = df["description"].fillna("")
    df["language_code"] = df["language_code"].fillna("")

    # book_file_path 기본값
    df["book_file_path"] = "/default/path/book.epub"

    # ISBN 정제
    df["isbn13"] = df["isbn13"].apply(clean_isbn)

    # UNIQUE 제약 때문에 ISBN 빈값은 NULL 처리
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
        "isbn13"
    ]

    df[cols].to_sql("book_tb", engine, if_exists="append", index=False, chunksize=10000)
    
    print(f"Inserted {len(df)} books.")
        
# --- (6) Tags 삽입 ---
def seed_tags(engine):
    print("Seeding tag_tb ...")
    df = pd.read_csv(TAGS_FILE)
    df = df.rename(columns={"Genre ID": "idx", "Genre Name": "name"})
    df.to_sql("tag_tb", engine, if_exists="append", index=False)
    print(f"Inserted {len(df)} tags.")

# --- (6) Book-Tag mapping 삽입 ---
def seed_book_tags(engine):
    print("Seeding book_tag_tb ...")
    df = pd.read_csv(BOOK_TAGS_FILE)
    df = df.rename(columns={"book_id": "book_idx", "genre_id": "tag_idx"})
    df[["book_idx", "tag_idx"]].to_sql("book_tag_tb", engine, if_exists="append", index=False, chunksize=10000)
    print(f"Inserted {len(df)} book-tag relations.")

# --- (7) Ratings 삽입 ---
def seed_ratings(engine):
    print("Seeding book_rating_tb ...")
    df = pd.read_csv(RATINGS_FILE)
    df = df.rename(columns={"user_id": "user_idx", "book_id": "book_idx", "rating": "rating"})
    
    # 1️⃣ DB에 실제로 존재하는 book idx 읽기
    valid_books = pd.read_sql("SELECT idx FROM book_tb", engine)["idx"].tolist()
    valid_books_set = set(valid_books)
    
    # 2️⃣ 유효한 rating만 남기기
    df = df[df["book_idx"].isin(valid_books_set)]
    
    df[["user_idx", "book_idx", "rating"]].to_sql(
        "book_rating_tb",
        engine,
        if_exists="append",
        index=False,
        chunksize=20000
    )

    print(f"✅ Inserted {len(df)} ratings.")
        
# --- (8) 실행 ---
if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    
    # 파일 존재 확인
    for f in [BOOKS_FILE, TAGS_FILE, BOOK_TAGS_FILE, RATINGS_FILE]:
        if not os.path.exists(f):
            print(f" Missing file: {f}")
            exit()

    max_user_idx = pd.read_csv(RATINGS_FILE)["user_id"].max()

    seed_fake_users(engine, max_user_idx)
    seed_books(engine)
    seed_tags(engine)
    seed_book_tags(engine)
    seed_ratings(engine)

    print(" All CSV data successfully inserted!")
