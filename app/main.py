from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import recommend_router

app = FastAPI(title="BookWheel Recommendation API", version="1.0.0")

# 3. CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    recommend_router.router,
    prefix="/api/v1/recommend",
    tags=["Recommend"],
)
