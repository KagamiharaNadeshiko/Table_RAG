from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from ..tasks import GLOBAL_TASK_QUEUE
from ..deps import merge_config


router = APIRouter()


class CleanupRequest(BaseModel):
    targets: List[str]
    yes: bool = True
    dry_run: bool = False
    remove_excel: Optional[bool] = True  # 兼容未来扩展


@router.post("")
def cleanup(req: CleanupRequest):
    body = req.dict()
    _ = merge_config(body)  # 预留：如需使用目录配置

    def task():
        # 重用现有脚本的主逻辑
        from offline_data_ingestion_and_query_interface.src.cleanup import run_cleanup
        code = run_cleanup(targets=req.targets, assume_yes=req.yes, dry_run=req.dry_run)
        return {"exit_code": code}

    task_id = GLOBAL_TASK_QUEUE.submit(task)
    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    res = GLOBAL_TASK_QUEUE.get(task_id)
    if not res:
        raise HTTPException(status_code=404, detail="task not found")
    return res


