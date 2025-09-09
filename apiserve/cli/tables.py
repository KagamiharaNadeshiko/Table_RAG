import argparse
import requests


def main():
    parser = argparse.ArgumentParser(description="List tables via API")
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--include-meta", action="store_true", help="Include per-table metadata like original_filename")
    parser.add_argument("--pretty", action="store_true", help="Pretty print table to original_filename mapping")
    parser.add_argument("--filenames-only", action="store_true", help="Print only original filenames, one per line")
    args = parser.parse_args()

    # --filenames-only implies we need metadata
    include_meta = args.include_meta or args.filenames_only
    params = {"include_meta": "true" if include_meta else "false"}
    r = requests.get(f"{args.host}/tables", params=params)
    r.raise_for_status()
    data = r.json()
    if args.filenames_only and isinstance(data, dict) and "meta" in data:
        for m in data.get("meta", []):
            print(m.get("original_filename"))
    elif args.pretty and include_meta and isinstance(data, dict) and "meta" in data:
        for m in data.get("meta", []):
            table = m.get("table") or m.get("table_name")
            original = m.get("original_filename")
            print(f"{table} => {original}")
    else:
        print(data)


if __name__ == "__main__":
    main()


