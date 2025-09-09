from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, List, Optional
import os
import sys
import io
from contextlib import redirect_stdout
from pathlib import Path

from ..deps import merge_config


router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    table_id: Optional[str] = "auto"  # or list in future
    tables: Optional[List[str]] = None
    doc_dir: Optional[str] = None
    excel_dir: Optional[str] = None
    bge_dir: Optional[str] = None
    embedding_policy: Optional[str] = None
    backbone: Optional[str] = None


@router.post("/ask")
def ask(req: ChatRequest):
    cfg = merge_config(req.dict())

    # 构造 argparse.Namespace 供 interactive_chat 使用
    class Args:
        pass

    args = Args()
    args.backbone = cfg.get("backbone")
    # 先定位项目根目录，再将路径参数标准化为绝对路径，防止 chdir 后相对路径失效
    project_root = Path(__file__).resolve().parents[2]
    def _abs(p: str | None) -> str | None:
        if not p:
            return p
        pp = Path(p)
        return str(pp if pp.is_absolute() else (project_root / pp))
    args.doc_dir = _abs(cfg.get("doc_dir"))
    args.excel_dir = _abs(cfg.get("excel_dir"))
    args.bge_dir = _abs(cfg.get("bge_dir"))
    args.max_iter = 5
    args.table_id = cfg.get("table_id") or "auto"
    args.question = cfg.get("question") or req.question
    args.tables = cfg.get("tables")
    args.embedding_policy = cfg.get("embedding_policy")
    args.verbose = False

    try:
        # 确保 `online_inference` 的相对导入可用：
        oi_dir = project_root / "online_inference"

        # 将 online_inference 加入 sys.path，并临时切换工作目录，
        # 以便其内部的 "from main import TableRAG" 这类相对顶层导入能成功。
        sys_path_added = False
        old_cwd = os.getcwd()
        try:
            if str(oi_dir) not in sys.path:
                sys.path.insert(0, str(oi_dir))
                sys_path_added = True
            os.chdir(str(oi_dir))

            from interactive_chat import interactive_chat  # noqa: E402

            # 捕获 stdout 中的答案文本（interactive_chat 会 print(answer)）
            buf = io.StringIO()
            with redirect_stdout(buf):
                interactive_chat(args)
            output = buf.getvalue().strip()
        finally:
            # 还原现场
            if sys_path_added and sys.path and sys.path[0] == str(oi_dir):
                sys.path.pop(0)
            os.chdir(old_cwd)

        # 返回最后一行非空文本作为答案（若无则返回整体）
        if output:
            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
            answer_text = lines[-1] if lines else output
        else:
            answer_text = ""

        return {"answer": answer_text}
    except Exception as e:
        import traceback as _tb
        err = f"{e}\n\n{_tb.format_exc()}"
        raise HTTPException(status_code=500, detail=err)


