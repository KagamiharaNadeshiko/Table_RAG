import argparse
import os
import sys
import requests


def main():
    parser = argparse.ArgumentParser(description="Upload multiple Excel files and optionally rebuild embeddings")
    parser.add_argument("--api", type=str, default="http://127.0.0.1:8000", help="API base url")
    parser.add_argument("--excel_dir", type=str, default="offline_data_ingestion_and_query_interface/dataset/dev_excel", help="Excel root dir on server")
    parser.add_argument("--files", type=str, nargs="+", required=True, help="Local excel file paths to upload")
    parser.add_argument("--rebuild", action="store_true", help="Call upload_and_rebuild_many after upload")
    parser.add_argument("--doc_dir", type=str, default=None)
    parser.add_argument("--bge_dir", type=str, default=None)
    parser.add_argument("--policy", type=str, default=None, choices=["rebuild","build_if_missing","load_only"])
    parser.add_argument("--save_path", type=str, default=None)

    args = parser.parse_args()

    # 1) upload_many
    url = f"{args.api}/data/upload_many"
    files_payload = [("files", (os.path.basename(p), open(p, "rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) for p in args.files]
    try:
        resp = requests.post(url, files=files_payload, data={"excel_dir": args.excel_dir}, timeout=600)
        resp.raise_for_status()
    finally:
        for _, fh, *_ in files_payload:
            try:
                fh.close()
            except Exception:
                pass

    print("upload_many:", resp.json())

    if not args.rebuild:
        return

    # 2) upload_and_rebuild_many (no need to re-upload: demonstrate single call flow)
    url2 = f"{args.api}/data/upload_and_rebuild_many"
    files_payload2 = [("files", (os.path.basename(p), open(p, "rb"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) for p in args.files]
    form = {
        "excel_dir": args.excel_dir,
    }
    if args.doc_dir:
        form["doc_dir"] = args.doc_dir
    if args.bge_dir:
        form["bge_dir"] = args.bge_dir
    if args.policy:
        form["policy"] = args.policy
    if args.save_path:
        form["save_path"] = args.save_path

    try:
        resp2 = requests.post(url2, files=files_payload2, data=form, timeout=3600)
        resp2.raise_for_status()
    finally:
        for _, fh, *_ in files_payload2:
            try:
                fh.close()
            except Exception:
                pass

    print("upload_and_rebuild_many:", resp2.json())


if __name__ == "__main__":
    main()


