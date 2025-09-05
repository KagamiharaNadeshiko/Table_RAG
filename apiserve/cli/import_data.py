import argparse
import time
import requests


def wait_task(base_url: str, task_id: str, timeout: int = 3600, interval: float = 1.0):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{base_url}/data/tasks/{task_id}")
        r.raise_for_status()
        data = r.json()
        if data.get("status") in ("succeeded", "failed"):
            return data
        time.sleep(interval)
    raise TimeoutError("Task wait timeout")


def main():
    parser = argparse.ArgumentParser(description="Import excel to DB via API")
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--excel_dir", default=None)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()

    payload = {"excel_dir": args.excel_dir}
    r = requests.post(f"{args.host}/data/import", json=payload)
    r.raise_for_status()
    info = r.json()
    print("queued:", info)
    if args.wait:
        done = wait_task(args.host, info["task_id"]) 
        print("done:", done)


if __name__ == "__main__":
    main()


