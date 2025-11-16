import pickle
import numpy as np
from pathlib import Path
from lightfm import LightFM
from app.core.config import settings

class LightFMModel:
    def __init__(
        self,
        model_path : Path = settings.MODEL_PATH,
        user_feat_path : Path = settings.USER_FEATURE_PATH,
        item_feat_path : Path = settings.ITEM_FEATURE_PATH,
    ):
        with open(model_path, "rb") as f:
            self.model : LightFM = pickle.load(f)
        
        self.user_features = np.load(user_feat_path)
        self.item_features = np.load(item_feat_path)
        
        # 크기 저장
        self.n_users = self.user_features.shape[0]
        self.n_items = self.item_features.shape[0]
        
lightfm_model = LightFMModel()

        