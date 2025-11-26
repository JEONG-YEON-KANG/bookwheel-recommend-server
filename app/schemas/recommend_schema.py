from pydantic import BaseModel
from typing import List


# 공통 응답 정의
class BookRecommendation(BaseModel):
    bookIdx: int
    score: float


class BookListResponse(BaseModel):
    recommendedBookList: List[BookRecommendation]


class UserListResponse(BaseModel):
    recommendedUserList: List[int]


# 개별 요청 (body) 정의
# 설문 기반 초기 추천
class RecommendInitRequest(BaseModel):
    genreList: List[int] = []
    moodList: List[int] = []
    purposeList: List[int] = []
    bookIdxList: List[int] = []
