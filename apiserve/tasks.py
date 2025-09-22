import threading
import uuid
import time
from typing import Any, Callable, Dict, Optional
import traceback


class TaskStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskRecord:
    def __init__(self, target: Callable[[], Any]):
        self.id = str(uuid.uuid4())
        self.target = target
        self.status = TaskStatus.QUEUED
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None


class InMemoryTaskQueue:
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = threading.RLock()

    def submit(self, target: Callable[[], Any]) -> str:
        record = TaskRecord(target)
        with self._lock:
            self._tasks[record.id] = record
        thread = threading.Thread(target=self._run_task, args=(record.id,), daemon=True)
        thread.start()
        return record.id

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks[task_id]
            record.status = TaskStatus.RUNNING
            record.started_at = time.time()
        try:
            result = record.target()
            with self._lock:
                record.result = result
                record.status = TaskStatus.SUCCEEDED
                record.ended_at = time.time()
        except Exception as e:
            tb = traceback.format_exc()
            with self._lock:
                record.error = f"{e}\n{tb}"
                record.status = TaskStatus.FAILED
                record.ended_at = time.time()

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._tasks.get(task_id)
            if not record:
                return None
            return {
                "task_id": record.id,
                "status": record.status,
                "result": record.result,
                "error": record.error,
                "created_at": record.created_at,
                "started_at": record.started_at,
                "ended_at": record.ended_at,
            }


GLOBAL_TASK_QUEUE = InMemoryTaskQueue()


