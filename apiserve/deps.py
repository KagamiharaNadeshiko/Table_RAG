import os
from typing import Any, Dict


# Resolve project root as the parent directory of this file's directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))

DEFAULTS = {
    "doc_dir": os.path.join("offline_data_ingestion_and_query_interface", "data", "schema"),
    "excel_dir": os.path.join("offline_data_ingestion_and_query_interface", "dataset", "dev_excel"),
    "bge_dir": os.path.join("online_inference", "bge_models"),
    "embedding_save_path": os.path.join("online_inference", "embedding.pkl"),
    "embedding_policy": "build_if_missing",
    "backbone": "qwen2.57b",
}


def _to_abs(path_value: str | None) -> str | None:
    if not path_value:
        return path_value
    # already absolute
    if os.path.isabs(path_value):
        return path_value
    # join with project root
    return os.path.normpath(os.path.join(PROJECT_ROOT, path_value))


def load_global_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    config_path = os.path.join(PROJECT_ROOT, "apiserve", "config.json")
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    # Merge with defaults first
    merged = {**DEFAULTS, **cfg}
    # Normalize known path fields to absolute
    merged["doc_dir"] = _to_abs(merged.get("doc_dir"))
    merged["excel_dir"] = _to_abs(merged.get("excel_dir"))
    merged["bge_dir"] = _to_abs(merged.get("bge_dir"))
    merged["embedding_save_path"] = _to_abs(merged.get("embedding_save_path"))
    return merged


def merge_config(body: Dict[str, Any] | None) -> Dict[str, Any]:
    base = load_global_config()
    if body:
        # Prefer non-None values from body
        merged = {**base, **{k: v for k, v in body.items() if v is not None}}
    else:
        merged = base
    # Normalize again in case request body supplied relative paths
    merged["doc_dir"] = _to_abs(merged.get("doc_dir"))
    merged["excel_dir"] = _to_abs(merged.get("excel_dir"))
    merged["bge_dir"] = _to_abs(merged.get("bge_dir"))
    merged["embedding_save_path"] = _to_abs(merged.get("embedding_save_path"))
    return merged


