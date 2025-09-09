import argparse
import requests


def main():
    parser = argparse.ArgumentParser(description="One-shot question via API")
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--question", required=True)
    parser.add_argument("--table_id", default="auto")
    parser.add_argument("--backbone", default=None)
    parser.add_argument("--embedding_policy", default=None)
    args = parser.parse_args()

    payload = {
        "question": args.question,
        "table_id": args.table_id,
        "backbone": args.backbone,
        "embedding_policy": args.embedding_policy,
    }
    r = requests.post(f"{args.host}/chat/ask", json=payload)
    r.raise_for_status()
    print(r.json())


if __name__ == "__main__":
    main()


