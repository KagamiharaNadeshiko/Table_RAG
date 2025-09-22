from fastapi import APIRouter
from typing import List
import os
import json

from ..deps import merge_config


router = APIRouter()


@router.get("")
def list_tables(doc_dir: str | None = None, excel_dir: str | None = None, include_meta: bool = False):
    cfg = merge_config({"doc_dir": doc_dir, "excel_dir": excel_dir})
    schema_dir = cfg.get("doc_dir")
    tables: List[str] = []
    metas: List[dict] = []
    if schema_dir and os.path.isdir(schema_dir):
        for filename in os.listdir(schema_dir):
            if filename.endswith(".json"):
                stem = os.path.splitext(filename)[0]
                tables.append(stem)
                if include_meta:
                    try:
                        with open(os.path.join(schema_dir, filename), "r", encoding="utf-8") as f:
                            data = json.load(f)
                        metas.append({
                            "table": stem,
                            "table_name": data.get("table_name"),
                            "original_filename": data.get("original_filename"),
                            "source_file_hash": data.get("source_file_hash")
                        })
                    except Exception:
                        metas.append({
                            "table": stem,
                            "table_name": stem,
                            "original_filename": None,
                            "source_file_hash": None
                        })
    result = {"tables": sorted(tables), "count": len(tables), "schema_dir": schema_dir}
    if include_meta:
        # Align metas to sorted order
        order = {t: i for i, t in enumerate(sorted(tables))}
        metas_sorted = sorted(metas, key=lambda m: order.get(m.get("table", ""), 0))
        result["meta"] = metas_sorted
    return result


