from pydantic import BaseModel, Field, ConfigDict
from typing import List


# 공통 응답 정의
class BookRecommendation(BaseModel):
    book_idx: int = Field(..., serialization_alias="bookIdx")
    score: float


class BookListResponse(BaseModel):
    recommend_book_list: List[BookRecommendation] = Field(
        ..., serialization_alias="recommendBookList"
    )


class UserListResponse(BaseModel):
    recommended_user_list: List[int] = Field(
        ..., serialization_alias="recommendedUserList"
    )


# 개별 요청 (body) 정의
# 설문 기반 초기 추천
class RecommendInitRequest(BaseModel):
    genre_list: List[int] = Field(default=[], serialization_alias="genreList")
    mood_list: List[int] = Field(default=[], serialization_alias="moodList")
    purpose_list: List[int] = Field(default=[], serialization_alias="purposeList")
    book_idx_list: List[int] = Field(default=[], serialization_alias="bookIdxList")

    model_config = ConfigDict(populate_by_name=True)
