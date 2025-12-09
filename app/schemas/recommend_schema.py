from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class BookItemOnly(BaseModel):
    book_idx: int = Field(..., alias="bookIdx", serialization_alias="bookIdx")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class UserListResponse(BaseModel):
    user_list: List[int] = Field(..., serialization_alias="userList")
    model_config = ConfigDict(populate_by_name=True)


class BookListResponse(BaseModel):
    book_list: List[BookItemOnly] = Field(..., serialization_alias="bookList")
    model_config = ConfigDict(populate_by_name=True)


class GenreSection(BaseModel):
    genre: str
    book_list: List[BookItemOnly] = Field(
        ..., alias="bookList", serialization_alias="bookList"
    )

    model_config = ConfigDict(populate_by_name=True)


class RecentSection(BaseModel):
    book_idx: int = Field(..., alias="bookIdx", serialization_alias="bookIdx")
    book_list: List[BookItemOnly] = Field(
        None, alias="bookList", serialization_alias="bookList"
    )

    model_config = ConfigDict(populate_by_name=True)


class HomeResponse(BaseModel):
    top1: BookItemOnly = Field(..., serialization_alias="top1")
    top10: List[BookItemOnly] = Field(..., serialization_alias="top10")

    # ✔ recentTop10을 장르 리스트처럼 완전히 리스트로 선언해야 함
    recent_top10: Optional[List[RecentSection]] = Field(
        default=None,
        alias="recentTop10",
        serialization_alias="recentTop10",
    )

    popular_top10: List[BookItemOnly] = Field(
        ..., alias="popularTop10", serialization_alias="popularTop10"
    )

    genre_section_list: List[GenreSection] = Field(
        ..., alias="genreSectionList", serialization_alias="genreSectionList"
    )

    model_config = ConfigDict(populate_by_name=True)
