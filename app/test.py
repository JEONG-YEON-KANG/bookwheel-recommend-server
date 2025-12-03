import os
import psycopg2
import requests
import re
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
from typing import Optional, Union  # Python 3.9 호환성을 위해 Optional, Union 추가

# 환경 변수 로드 (.env 파일에서 API 키 가져오기)
load_dotenv()

# Google Books API 키
API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")


# -------------------------------
# DB 연결
# -------------------------------
def get_conn():
    """PostgreSQL 데이터베이스 연결을 설정합니다."""
    return psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="1234",
        database="bookwheel",
    )


# -------------------------------
# 제목 정제
# -------------------------------
def clean_title(title: str) -> str:
    """제목에서 시리즈 정보 등 불필요한 괄호 내용을 제거하여 검색 정확도를 높입니다."""
    if title:
        title = re.sub(r"\s*\(.*\)", "", title).strip()
    return title


# -------------------------------
# 1단계: ISBN13으로 원서 정보 가져오기
# -------------------------------
def get_original_book_info_by_isbn(isbn13: str) -> Optional[dict]:
    """ISBN13을 사용하여 Google Books API에서 원서의 정확한 정보를 가져옵니다."""
    if not isbn13:
        return None

    query = f"isbn:{isbn13}"
    url = "https://www.googleapis.com/books/v1/volumes"

    params = {"q": query, "maxResults": 1, "key": API_KEY}

    try:
        res = requests.get(url, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()

        items = data.get("items")
        if not items:
            return None

        info = items[0].get("volumeInfo", {})

        title = info.get("title", "")
        authors = info.get("authors", [])

        if title and authors:
            return {"title": clean_title(title), "author": authors[0]}

        return None
    except requests.exceptions.RequestException as e:
        print(f"ISBN Search Error: {e}")
        return None
    except Exception as e:
        print(f"ISBN General Error: {e}")
        return None


# -------------------------------
# 2단계: 저자 정보로 한국어 번역본 찾기 (유연성 최대화)
# -------------------------------
def find_korean_translation_by_info(title: str, author: str) -> list:
    """
    클린된 원저자 이름만을 사용하여 해당 저자의 모든 한국어 번역본을 검색합니다.
    """
    # 쿼리를 오직 저자 이름만으로 구성하여 가장 광범위한 결과를 얻습니다.
    query = f"{author}"

    url = "https://www.googleapis.com/books/v1/volumes"

    params = {
        "q": query,
        "langRestrict": "ko",  # 한국어 번역본으로 제한
        "maxResults": 40,  # 후보군을 40개로 늘림
        "key": API_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=5)
        res.raise_for_status()
        data = res.json()
        return data.get("items", [])
    except requests.exceptions.RequestException as e:
        return []
    except Exception as e:
        return []


# -------------------------------
# 번역본 필터링 및 선정 (기존과 동일)
# -------------------------------
def pick_best_korean_book(
    items: list, original_title: str, original_author: str
) -> Optional[dict]:
    """
    검색 결과 목록에서 가장 적합한 한국어 번역본을 선정합니다.
    """
    candidates = []

    for item in items:
        info = item.get("volumeInfo", {})

        if info.get("language") != "ko":
            continue

        title = info.get("title", "")
        authors = info.get("authors", [""])
        author_string = ", ".join(authors)

        # 불필요한 항목 제외 (해설서, 요약본 등)
        bad_words = ["해설", "요약", "워크북", "그래픽", "study", "analysis", "summary"]
        if any(bw.lower() in title.lower() for bw in bad_words):
            continue

        # 1. 제목 유사도 계산 (주요 점수)
        title_score = fuzz.partial_ratio(original_title.lower(), title.lower())

        # 2. 저자 유사도 계산 (보너스 점수)
        author_match_score = fuzz.partial_ratio(
            original_author.lower(), author_string.lower()
        )

        # 최종 점수 계산: 제목 유사도(주요) + 저자 유사도의 10% (보조)
        final_score = title_score + (author_match_score / 10)

        candidates.append(
            (
                final_score,
                {
                    "title": title,
                    "authors": author_string,
                    "cover": info.get("imageLinks", {}).get("thumbnail", None),
                    "score": final_score,
                },
            )
        )

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# -------------------------------
# DB 업데이트 (기존과 동일)
# -------------------------------
def update_book(idx: int, data: dict):
    """
    찾아낸 한국어 번역본 정보를 book_tb 테이블에 업데이트합니다.
    """
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE book_tb
            SET korean_title = %s,
                korean_author = %s,
                korean_cover_path = %s
            WHERE idx = %s
        """,
            (data["title"], data["authors"], data["cover"], idx),
        )

        conn.commit()
    except Exception as e:
        print(f"DB Update Error for idx {idx}: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# -------------------------------
# 전체 실행 로직 (ISBN13 우선 처리)
# -------------------------------
def run():
    """DB의 모든 책을 순회하며 ISBN13을 사용하여 번역본을 찾고 업데이트합니다."""
    conn = get_conn()
    cur = conn.cursor()

    # ❗ 컬럼 이름을 'isbn13'으로 명시하여 가져옵니다.
    cur.execute("""SELECT idx, title, author, isbn13 FROM book_tb ORDER BY idx""")
    rows = cur.fetchall()

    print(f"총 {len(rows)}권 처리 시작\n")

    for idx, db_title, db_author, isbn13 in rows:

        # 원서 검색에 사용할 제목과 저자 초기화 (DB 값으로 시작)
        search_title = db_title
        search_author = db_author.split(",")[0].strip() if db_author else ""

        print(f"===== [{idx}] {db_title} | {search_author} | ISBN13: {isbn13} =====")

        # 1단계: ISBN13이 있다면, ISBN13을 사용하여 가장 정확한 원서 정보 가져오기
        if isbn13:
            original_info = get_original_book_info_by_isbn(isbn13)

            if original_info:
                search_title = original_info["title"]
                search_author = original_info["author"]
                print(
                    f"INFO: ISBN13으로 원서 정보 갱신됨 -> 제목: {search_title}, 저자: {search_author}"
                )
            else:
                print("WARN: ISBN13 검색 실패. DB에 저장된 정보로 대체 검색 시도.")

        # 2단계: 갱신된(혹은 DB의) 정보로 한국어 번역본 검색 (저자 기반)
        items = find_korean_translation_by_info(search_title, search_author)

        # 3단계: 번역본 필터링 및 선정
        # 주의: 비교 대상은 DB 원제가 아니라 '갱신된 원제(search_title)'입니다.
        result = pick_best_korean_book(items, search_title, search_author)

        # 유사도 점수 50점 이상인 경우에만 업데이트
        if result and result.get("score", 0) > 50:
            print(f"✔ 번역본 발견 (유사도 {result['score']:.2f}): {result['title']}")
            update_book(idx, result)
        else:
            score_display = result["score"] if result else 0
            print(f"❌ 번역본 없음 (유사도 {score_display:.2f} < 50 또는 결과 없음)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    run()
