import os
from typing import Any, Dict


DEFAULTS = {
    "doc_dir": os.path.join("offline_data_ingestion_and_query_interface", "data", "schema"),
    "excel_dir": os.path.join("offline_data_ingestion_and_query_interface", "dataset", "dev_excel"),
    "bge_dir": os.path.join("online_inference", "bge_models"),
    "embedding_save_path": os.path.join("online_inference", "embedding.pkl"),
    "embedding_policy": "build_if_missing",
    "backbone": "qwen2.57b",
}


def load_global_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    config_path = os.path.join("apiserve", "config.json")
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    return {**DEFAULTS, **cfg}


def merge_config(body: Dict[str, Any] | None) -> Dict[str, Any]:
    base = load_global_config()
    if body:
        merged = {**base, **{k: v for k, v in body.items() if v is not None}}
    else:
        merged = base
    return merged


