from fastapi import APIRouter, Body, Header, Depends, Path, Request
from typing import Annotated, Optional

from app.services.recommend_service import RecommendService
from app.schemas.recommend_schema import (
    BookListResponse,
    UserListResponse,
    HomeResponse,
    BookItemOnly,
)

router = APIRouter(prefix="/recommend", tags=["Recommend"])


def get_recommend_service(request: Request) -> RecommendService:
    return request.app.state.recommend_service


# =========================================================
# 홈 화면 종합 추천
# warm/cold 및 설문 데이터 기반 통합 처리
# ========================================================


@router.get("/home", response_model=HomeResponse)
async def get_home_recommend(
    user_idx: Annotated[int, Header(alias="X-User-Idx")] = ...,
    service: RecommendService = Depends(get_recommend_service),
):
    response_data = service.get_home_recommend(
        user_idx,
    )
    return response_data


# =========================================================
# 유사 도서 추천
# ========================================================
@router.post("/books/{idx}", response_model=BookListResponse)
async def recomend_similar_book(
    book_idx: Annotated[int, Path(alias="idx")],
    service: RecommendService = Depends(get_recommend_service),
):
    k = 10
    results = service.recommend_similar_book(book_idx, k)
    book_list = [BookItemOnly(book_idx=r["book_idx"]) for r in results]

    return {"book_list": book_list}


# =========================================================
# 유사 유저 추천
# ========================================================
@router.get("/users/{idx}", response_model=UserListResponse)
async def recommend_similar_user(
    user_idx: Annotated[int, Path(alias="idx")],
    service: RecommendService = Depends(get_recommend_service),
):
    k = 10
    results = service.recommend_similar_user(user_idx, k)
    user_list = [r["user_idx"] for r in results]

    return {"user_list": user_list}
