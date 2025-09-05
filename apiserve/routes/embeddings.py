from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

from ..tasks import GLOBAL_TASK_QUEUE
from ..deps import merge_config


router = APIRouter()


class EmbeddingBuildRequest(BaseModel):
    doc_dir: Optional[str] = None
    excel_dir: Optional[str] = None
    bge_dir: Optional[str] = None
    save_path: Optional[str] = None
    policy: Optional[str] = None  # rebuild | build_if_missing | load_only


@router.post("/build")
def build_embeddings(req: EmbeddingBuildRequest):
    cfg = merge_config(req.dict())
    doc_dir = cfg.get("doc_dir")
    excel_dir = cfg.get("excel_dir")
    bge_dir = cfg.get("bge_dir")
    # 默认 save_path 固定到 online_inference/embedding.pkl
    default_save_path = os.path.join("online_inference", "embedding.pkl")
    save_path = (cfg.get("embedding_save_path") if not req.save_path else req.save_path) or default_save_path
    # 默认策略为 rebuild
    policy = (cfg.get("embedding_policy") if not req.policy else req.policy) or "rebuild"

    def task():
        from online_inference.embed_index import main as embed_main
        import sys
        argv = [
            "--doc_dir", doc_dir,
            "--excel_dir", excel_dir,
            "--bge_dir", bge_dir,
            "--save_path", save_path,
            "--policy", policy,
        ]
        # 直接调用其入口的解析器：临时替换 sys.argv
        prev = list(sys.argv)
        try:
            sys.argv = ["embed_index.py", *argv]
            embed_main()
        finally:
            sys.argv = prev
        return {"save_path": save_path, "policy": policy}

    task_id = GLOBAL_TASK_QUEUE.submit(task)
    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    res = GLOBAL_TASK_QUEUE.get(task_id)
    if not res:
        raise HTTPException(status_code=404, detail="task not found")
    return res


