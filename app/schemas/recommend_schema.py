from pydantic import BaseModel
from typing import List

# 공통 응답 정의
class BookListResponse(BaseModel):
    recommendedBookList : List[int]

class UserListResponse(BaseModel):
    recommendedUserList : List[int]

# 개별 요청 (body) 정의
# 설문 기반 초기 추천 
class RecommendInitRequest(BaseModel):
    genreList : List[int]