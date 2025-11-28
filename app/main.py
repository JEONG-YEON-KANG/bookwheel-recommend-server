from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import recommend_router
from app.services.recommend_service import RecommendService


# ================================
# lifespan에서 RecommendService 초기화
# ================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.recommend_service = RecommendService()
    except Exception as e:
        raise e

    yield


# ================================
# FastAPI 앱 생성 (한 번)
# ================================
app = FastAPI(
    title="BookWheel Recommendation API",
    version="1.0.0",
    lifespan=lifespan,
)

# ================================
# CORS 설정
# ================================
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# router 등록
# ================================
app.include_router(
    recommend_router.router,
    prefix="/api/v1/recommend",
    tags=["Recommend"],
)
