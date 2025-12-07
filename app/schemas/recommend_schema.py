from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


# 홈 화면 요청
class RecommendInitRequest(BaseModel):
    genre_list: List[int] = Field(default=[], serialization_alias="genreList")
    mood_list: List[int] = Field(default=[], serialization_alias="moodList")
    purpose_list: List[int] = Field(default=[], serialization_alias="purposeList")
    book_idx_list: List[int] = Field(default=[], serialization_alias="bookIdxList")

    model_config = ConfigDict(populate_by_name=True)


# 홈 화면 및 책 리스트 내부 항목
class BookItemOnly(BaseModel):
    book_idx: int = Field(..., serialization_alias="bookIdx")
    model_config = ConfigDict(populate_by_name=True)


# 유사 유저 추천 응답 스키마
class UserListResponse(BaseModel):
    user_list: List[int] = Field(..., serialization_alias="userList")
    model_config = ConfigDict(populate_by_name=True)


# 유사 도서 추천 응답 스키마
class BookListResponse(BaseModel):
    book_list: List[BookItemOnly] = Field(..., serialization_alias="bookList")
    model_config = ConfigDict(populate_by_name=True)


# 장르 섹션 정의
class GenreSection(BaseModel):
    genre: str
    book_list: List[BookItemOnly] = Field(..., serialization_alias="bookList")


# 홈 화면 최종 응답 스키마
class HomeResponse(BaseModel):
    top1: BookItemOnly = Field(..., serialization_alias="top1")
    top10: List[BookItemOnly] = Field(..., serialization_alias="top10")
    # recent 이력 없을 시 누락
    recent_top10: Optional[List[BookItemOnly]] = Field(
        None, serialization_alias="recentTop10"
    )
    # 공통
    popular_top10: List[BookItemOnly] = Field(..., serialization_alias="popularTop10")
    genre_section_list: List[GenreSection] = Field(
        ..., serialization_alias="genreSectionList"
    )

    model_config = ConfigDict(populate_by_name=True)
