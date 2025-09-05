import argparse
import time
import requests


def wait_task(base_url: str, task_id: str, timeout: int = 1800, interval: float = 1.0):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{base_url}/embeddings/tasks/{task_id}")
        r.raise_for_status()
        data = r.json()
        if data.get("status") in ("succeeded", "failed"):
            return data
        time.sleep(interval)
    raise TimeoutError("Task wait timeout")


def main():
    parser = argparse.ArgumentParser(description="Build/load embeddings via API")
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--doc_dir")
    parser.add_argument("--excel_dir")
    parser.add_argument("--bge_dir")
    parser.add_argument("--save_path", default=None)
    parser.add_argument("--policy", default=None, choices=["rebuild", "build_if_missing", "load_only"])
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()

    payload = {
        "doc_dir": args.doc_dir,
        "excel_dir": args.excel_dir,
        "bge_dir": args.bge_dir,
        "save_path": args.save_path,
        "policy": args.policy,
    }
    r = requests.post(f"{args.host}/embeddings/build", json=payload)
    r.raise_for_status()
    info = r.json()
    print("queued:", info)
    if args.wait:
        done = wait_task(args.host, info["task_id"]) 
        print("done:", done)


if __name__ == "__main__":
    main()


