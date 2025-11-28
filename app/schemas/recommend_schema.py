from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


# HomeRsponse의 내부 항목 정의
class HomeBookItem(BaseModel):
    book_idx: int = Field(..., serialization_alias="bookIdx")


# 장르 섹션 정의
class GenreSection(BaseModel):
    genre: str
    book_list: List[HomeBookItem] = Field(..., serialization_alias="bookList")


# 홈 화면 최종 응답 스키마
class HomeResponse(BaseModel):
    # warm user
    personal_top1: Optional[HomeBookItem] = Field(
        None, serialization_alias="personalTop1"
    )
    personal_top10: Optional[List[HomeBookItem]] = Field(
        None, serialization_alias="personalTop10"
    )
    # cold user
    initial_top1: Optional[HomeBookItem] = Field(
        None, serialization_alias="initialTop1"
    )
    initial_top10: Optional[List[HomeBookItem]] = Field(
        None, serialization_alias="initialTop10"
    )
    # recent 이력 없을 시 누락
    recent_top10: Optional[List[HomeBookItem]] = Field(
        None, serialization_alias="recentTop10"
    )
    # 공통
    popular_top10: List[HomeBookItem] = Field(..., serialization_alias="popularTop10")
    genre_section_list: List[GenreSection] = Field(
        ..., serialization_alias="genreSectionList"
    )

    model_config = ConfigDict(populate_by_name=True)
