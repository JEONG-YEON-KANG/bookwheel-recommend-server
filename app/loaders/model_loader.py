import pickle
import numpy as np
from pathlib import Path
from lightfm import LightFM
from app.config.settings import settings


class LightFMModel:
    def __init__(
        self,
        model_path: Path = settings.MODEL_PATH,
        dataset_path: Path = settings.DATASET_PATH,
        item_feat_path: Path = settings.ITEM_FEATURE_PATH,
    ):
        with open(model_path, "rb") as f:
            self.model: LightFM = pickle.load(f)

        with open(dataset_path, "rb") as f:
            self.dataset = pickle.load(f)

        with open(item_feat_path, "rb") as f:
            self.item_features = pickle.load(f)

        # 매핑
        self.user_id_map = self.dataset._user_id_mapping
        self.item_id_map = self.dataset._item_id_mapping

        self.rev_user_id_map = {v: k for k, v in self.user_id_map.items()}
        self.rev_item_id_map = {v: k for k, v in self.item_id_map.items()}

        self.n_users = len(self.user_id_map)
        self.n_items = len(self.item_id_map)


light = LightFMModel()
