import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    MODEL_PATH = Path(os.getenv("MODEL_PATH"))
    DATASET_PATH = Path(os.getenv("DATASET_PATH"))
    ITEM_FEATURE_PATH = Path(os.getenv("ITEM_FEATURE_PATH"))


settings = Settings()
