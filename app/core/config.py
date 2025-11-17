import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    MODEL_PATH = BASE_DIR / os.getenv("MODEL_PATH")
    DATASET_PATH = BASE_DIR / os.getenv("DATASET_PATH")
    ITEM_FEATURE_PATH = BASE_DIR / os.getenv("ITEM_FEATURE_PATH")
    BOOK_META_PATH = BASE_DIR / os.getenv("BOOK_META_PATH")
    
settings = Settings()