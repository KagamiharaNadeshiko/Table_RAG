from fastapi import APIRouter, HTTPException
from fastapi import UploadFile, File, Form
import os
import uuid
from pydantic import BaseModel
from typing import Optional, List

from ..tasks import GLOBAL_TASK_QUEUE
from ..deps import merge_config


router = APIRouter()


class ImportRequest(BaseModel):
    excel_dir: Optional[str] = None


@router.get("/dirs")
def get_dirs(excel_dir: Optional[str] = None, doc_dir: Optional[str] = None, bge_dir: Optional[str] = None, save_path: Optional[str] = None):
    cfg = merge_config({
        "excel_dir": excel_dir,
        "doc_dir": doc_dir,
        "bge_dir": bge_dir,
        "embedding_save_path": save_path,
    })
    return {
        "excel_dir": cfg.get("excel_dir"),
        "doc_dir": cfg.get("doc_dir"),
        "bge_dir": cfg.get("bge_dir"),
        "embedding_save_path": cfg.get("embedding_save_path"),
    }


@router.post("/import")
def run_import(req: ImportRequest):
    cfg = merge_config(req.dict())
    excel_dir = cfg.get("excel_dir")

    def task():
        from offline_data_ingestion_and_query_interface.src.data_persistent import parse_excel_file_and_insert_to_db
        # 此函数内部会读取 DEFAULT 的 dev_excel 目录；这里传参以适配
        return parse_excel_file_and_insert_to_db(excel_dir)

    task_id = GLOBAL_TASK_QUEUE.submit(task)
    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    res = GLOBAL_TASK_QUEUE.get(task_id)
    if not res:
        raise HTTPException(status_code=404, detail="task not found")
    return res
@router.post("/upload")
async def upload_excel(file: UploadFile = File(...), excel_dir: Optional[str] = Form(None)):
    # 解析配置，拿到目标根目录
    cfg = merge_config({"excel_dir": excel_dir})
    dest_root = cfg.get("excel_dir")
    if not dest_root:
        raise HTTPException(status_code=400, detail="excel_dir is not configured")

    # 保存上传的文件到 excel_dir 根目录
    os.makedirs(dest_root, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    lower_name = safe_name.lower()
    if not (lower_name.endswith(".xlsx") or lower_name.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx or .xls files are supported")
    saved_path = os.path.join(dest_root, safe_name)
    try:
        with open(saved_path, "wb") as fout:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                fout.write(chunk)
    finally:
        await file.close()

    # 不再对 .xls 进行转换，保留原始文件

    # 提交异步任务：处理 excel_dir 根目录（新文件会被发现并导入）
    def task():
        from offline_data_ingestion_and_query_interface.src.data_persistent import parse_excel_file_and_insert_to_db
        return parse_excel_file_and_insert_to_db(dest_root)

    task_id = GLOBAL_TASK_QUEUE.submit(task)
    return {"task_id": task_id, "status": "queued", "saved_path": saved_path}



@router.post("/upload_many")
async def upload_excel_many(files: List[UploadFile] = File(...), excel_dir: Optional[str] = Form(None)):
    # 解析配置，拿到目标根目录
    cfg = merge_config({"excel_dir": excel_dir})
    dest_root = cfg.get("excel_dir")
    if not dest_root:
        raise HTTPException(status_code=400, detail="excel_dir is not configured")

    os.makedirs(dest_root, exist_ok=True)

    saved_paths = []
    for file in files:
        safe_name = os.path.basename(file.filename)
        lower_name = safe_name.lower()
        if not (lower_name.endswith(".xlsx") or lower_name.endswith(".xls")):
            await file.close()
            raise HTTPException(status_code=400, detail="Only .xlsx or .xls files are supported")
        saved_path = os.path.join(dest_root, safe_name)
        try:
            with open(saved_path, "wb") as fout:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    fout.write(chunk)
        finally:
            await file.close()
        # 不再对 .xls 进行转换，保留原始文件
        saved_paths.append(saved_path)

    # 提交异步任务：处理 excel_dir 根目录（新文件会被发现并导入）
    def task():
        from offline_data_ingestion_and_query_interface.src.data_persistent import parse_excel_file_and_insert_to_db
        return parse_excel_file_and_insert_to_db(dest_root)

    task_id = GLOBAL_TASK_QUEUE.submit(task)
    return {"task_id": task_id, "status": "queued", "saved_paths": saved_paths}



@router.post("/upload_and_rebuild")
async def upload_and_rebuild(
    file: UploadFile = File(...),
    excel_dir: Optional[str] = Form(None),
    policy: Optional[str] = Form(None),
    save_path: Optional[str] = Form(None),
    doc_dir: Optional[str] = Form(None),
    bge_dir: Optional[str] = Form(None),
):
    # 解析配置，拿到目标根目录与嵌入默认参数
    cfg = merge_config({
        "excel_dir": excel_dir,
        "embedding_policy": policy,
        "embedding_save_path": save_path,
        "doc_dir": doc_dir,
        "bge_dir": bge_dir,
    })
    dest_root = cfg.get("excel_dir")
    if not dest_root:
        raise HTTPException(status_code=400, detail="excel_dir is not configured")

    os.makedirs(dest_root, exist_ok=True)

    # 保存到 excel_dir 根目录
    safe_name = os.path.basename(file.filename)
    lower_name = safe_name.lower()
    if not (lower_name.endswith(".xlsx") or lower_name.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx or .xls files are supported")
    saved_path = os.path.join(dest_root, safe_name)
    try:
        with open(saved_path, "wb") as fout:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                fout.write(chunk)
    finally:
        await file.close()

    # 不再对 .xls 进行转换，保留原始文件

    # 读取用于构建嵌入的最终参数（含默认）
    final_doc_dir = cfg.get("doc_dir")
    final_excel_dir = cfg.get("excel_dir")
    final_bge_dir = cfg.get("bge_dir")
    # 默认 save_path 固定到 online_inference/embedding.pkl
    default_save_path = os.path.join("online_inference", "embedding.pkl")
    final_save_path = (cfg.get("embedding_save_path") if not save_path else save_path) or default_save_path
    final_policy = (cfg.get("embedding_policy") if not policy else policy) or "rebuild"

    # 串行后台任务：1) 持久化 2) 重建向量（等价于 CLI embeddings 路由的内部逻辑）
    def task():
        from offline_data_ingestion_and_query_interface.src.data_persistent import parse_excel_file_and_insert_to_db
        from online_inference.embed_index import main as embed_main
        import sys

        # Step 1: 导入/持久化
        parse_excel_file_and_insert_to_db(final_excel_dir)

        # Step 2: 构建/重建嵌入
        argv = [
            "--doc_dir", final_doc_dir,
            "--excel_dir", final_excel_dir,
            "--bge_dir", final_bge_dir,
            "--save_path", final_save_path,
            "--policy", final_policy,
        ]
        prev = list(sys.argv)
        try:
            sys.argv = ["embed_index.py", *argv]
            embed_main()
        finally:
            sys.argv = prev

        return {
            "save_path": final_save_path,
            "policy": final_policy,
            "excel_dir": final_excel_dir,
            "doc_dir": final_doc_dir,
        }

    task_id = GLOBAL_TASK_QUEUE.submit(task)
    return {"task_id": task_id, "status": "queued", "saved_path": saved_path}


@router.post("/upload_and_rebuild_many")
async def upload_and_rebuild_many(
    files: List[UploadFile] = File(...),
    excel_dir: Optional[str] = Form(None),
    policy: Optional[str] = Form(None),
    save_path: Optional[str] = Form(None),
    doc_dir: Optional[str] = Form(None),
    bge_dir: Optional[str] = Form(None),
):
    # 解析配置，拿到目标根目录与嵌入默认参数
    cfg = merge_config({
        "excel_dir": excel_dir,
        "embedding_policy": policy,
        "embedding_save_path": save_path,
        "doc_dir": doc_dir,
        "bge_dir": bge_dir,
    })
    dest_root = cfg.get("excel_dir")
    if not dest_root:
        raise HTTPException(status_code=400, detail="excel_dir is not configured")

    os.makedirs(dest_root, exist_ok=True)

    saved_paths = []
    for file in files:
        safe_name = os.path.basename(file.filename)
        lower_name = safe_name.lower()
        if not (lower_name.endswith(".xlsx") or lower_name.endswith(".xls")):
            await file.close()
            raise HTTPException(status_code=400, detail="Only .xlsx or .xls files are supported")
        saved_path = os.path.join(dest_root, safe_name)
        try:
            with open(saved_path, "wb") as fout:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    fout.write(chunk)
        finally:
            await file.close()
        # 不再对 .xls 进行转换，保留原始文件
        saved_paths.append(saved_path)

    # 读取用于构建嵌入的最终参数（含默认）
    final_doc_dir = cfg.get("doc_dir")
    final_excel_dir = cfg.get("excel_dir")
    final_bge_dir = cfg.get("bge_dir")
    # 默认 save_path 固定到 online_inference/embedding.pkl
    default_save_path = os.path.join("online_inference", "embedding.pkl")
    final_save_path = (cfg.get("embedding_save_path") if not save_path else save_path) or default_save_path
    final_policy = (cfg.get("embedding_policy") if not policy else policy) or "rebuild"

    # 串行后台任务：1) 持久化 2) 重建向量
    def task():
        from offline_data_ingestion_and_query_interface.src.data_persistent import parse_excel_file_and_insert_to_db
        from online_inference.embed_index import main as embed_main
        import sys

        # Step 1: 导入/持久化
        parse_excel_file_and_insert_to_db(final_excel_dir)

        # Step 2: 构建/重建嵌入
        argv = [
            "--doc_dir", final_doc_dir,
            "--excel_dir", final_excel_dir,
            "--bge_dir", final_bge_dir,
            "--save_path", final_save_path,
            "--policy", final_policy,
        ]
        prev = list(sys.argv)
        try:
            sys.argv = ["embed_index.py", *argv]
            embed_main()
        finally:
            sys.argv = prev

        return {
            "save_path": final_save_path,
            "policy": final_policy,
            "excel_dir": final_excel_dir,
            "doc_dir": final_doc_dir,
        }

    task_id = GLOBAL_TASK_QUEUE.submit(task)
    return {"task_id": task_id, "status": "queued", "saved_paths": saved_paths}
