
## 快速開始（Quick Start）

1. 安裝依賴

```bash
pip install -r requirements.txt
```

1. 啟動服務（PowerShell）

```powershell
uvicorn apiserve.main:app --host 127.0.0.1 --port 8000 --reload
```

1. 健康檢查：瀏覽器或 CLI 請求 `GET /health`

1. 打開互動式文件：前往 `http://127.0.0.1:8000/docs`

## 常見操作（Recipes）

- 清理（依 Excel 名稱移除對應表/Schema/Excel）：

```bash
python apiserve/cli/cleanup.py --target 銷售統計2023.xlsx --yes --wait
```

- 從目錄導入資料：

```bash
python apiserve/cli/import_data.py --wait
```

- 建立/重建向量索引（預設 policy=rebuild，save_path=online_inference/embedding.pkl）：

```bash
python apiserve/cli/embeddings.py --doc_dir offline_data_ingestion_and_query_interface/data/schema --excel_dir offline_data_ingestion_and_query_interface/dataset/dev_excel --bge_dir online_inference/bge_models --policy rebuild --wait
```

- 上傳並重建（multipart/form-data）：

```bash
curl -X POST http://127.0.0.1:8000/data/upload_and_rebuild \
  -F "excel_dir=offline_data_ingestion_and_query_interface/dataset/dev_excel" \
  -F "policy=rebuild" \
  -F "file=@your.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

- 多檔上傳（僅導入）：

```bash
curl -X POST http://127.0.0.1:8000/data/upload_many \
  -F "excel_dir=offline_data_ingestion_and_query_interface/dataset/dev_excel" \
  -F "files=@a.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  -F "files=@b.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

- 多檔上傳並重建：

```bash
curl -X POST http://127.0.0.1:8000/data/upload_and_rebuild_many \
  -F "excel_dir=offline_data_ingestion_and_query_interface/dataset/dev_excel" \
  -F "policy=rebuild" \
  -F "files=@a.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  -F "files=@b.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

- 以 Python 腳本批次上傳：

```bash
python apiserve/cli/multi_upload.py --files offline_data_ingestion_and_query_interface/dataset/dev_excel/a.xlsx offline_data_ingestion_and_query_interface/dataset/dev_excel/b.xlsx --rebuild
```

- 提問（非串流）：

```bash
python apiserve/cli/chat.py --question "这张表说明了什么内容？" --table_id 鈺創科技財報資料.xlsx                                
```

- 列出當前表：

```bash
python apiserve/cli/tables.py
```

## 路由概覽（Endpoints）

- POST `/cleanup`：按 Excel 名稱刪除對應表、Schema、Excel（包含 DROP TABLE）
- GET `/cleanup/tasks/{task_id}`：查詢清理任務狀態
- POST `/data/import`：導入 Excel 至資料庫並產生 Schema
- POST `/data/upload`：上傳單一 Excel，立即觸發導入（掃描 excel_dir 根目錄）
- POST `/data/upload_many`：上傳多個 Excel，立即觸發導入（掃描 excel_dir 根目錄）
- POST `/data/upload_and_rebuild`：上傳 Excel → 導入 → 觸發向量重建
- POST `/data/upload_and_rebuild_many`：上傳多個 Excel → 導入 → 觸發向量重建
- GET `/data/tasks/{task_id}`：查詢導入任務狀態
- POST `/embeddings/build`：建立/載入向量索引
- GET `/embeddings/tasks/{task_id}`：查詢嵌入任務狀態
- GET `/tables`：列出 Schema 目錄中的表名
- POST `/chat/ask`：一次性問答（非串流）

## 上傳方式總覽

- 單檔上傳並觸發導入：`POST /data/upload`
  - 表單：`file`（Excel 檔）、可選 `excel_dir`
  - 行為：儲存至 `excel_dir` → 觸發目錄導入

- 多檔上傳並觸發導入：`POST /data/upload_many`
  - 表單：`files`（多個 Excel 檔）、可選 `excel_dir`
  - 行為：儲存多檔 → 觸發目錄導入

- 單檔上傳並重建向量：`POST /data/upload_and_rebuild`
  - 表單：`file`、可選 `excel_dir`、`policy`、`save_path`、`doc_dir`、`bge_dir`
  - 行為：儲存 → 導入 → 建立/重建向量索引

- 多檔上傳並重建向量：`POST /data/upload_and_rebuild_many`
  - 表單：`files`、可選 `excel_dir`、`policy`、`save_path`、`doc_dir`、`bge_dir`
  - 行為：儲存多檔 → 導入 → 建立/重建向量索引

## 組態（Config）

- 預設值（源自 `apiserve/deps.py`）：
  - **doc_dir**: `offline_data_ingestion_and_query_interface/data/schema`
  - **excel_dir**: `offline_data_ingestion_and_query_interface/dataset/dev_excel`
  - **bge_dir**: `online_inference/bge_models`
  - **embedding_save_path**: `online_inference/embedding.pkl`
  - **embedding_policy**: `build_if_missing`
  - **backbone**: `qwen2.57b`

說明：請求中的欄位若為 `null`/未提供，則採用全域組態合併後的預設值；若提供非空值，則以請求覆寫。

## 任務查詢約定（Tasks）

- 以記憶體佇列非同步執行（`apiserve/tasks.py`）。建立任務會回傳 `task_id` 與 `status=queued`。
- 透過對應模組的 `GET /.../tasks/{task_id}` 查詢任務狀態：`queued`、`running`、`succeeded`、`failed`，以及可選的 `result`/`error`。

## API 參考

### 健康檢查

- GET `/health`
  - 回應：`{"status": "ok", "version": "0.1.0"}`

### 清理 Cleanup

- POST `/cleanup`
  - Request JSON：
    - **targets**: string[]（必填）Excel 檔名列表（例如 `銷售統計2023.xlsx`），據此刪除對應表/Schema/Excel
    - **yes**: boolean（預設 true）確認執行
    - **dry_run**: boolean（預設 false）僅演練
    - **remove_excel**: boolean（保留欄位，預設 true）
  - 回應：`{"task_id": string, "status": "queued"}`

- GET `/cleanup/tasks/{task_id}`
  - 回應：任務狀態紀錄，含 `status`、`result`（如 `{"exit_code": 0}`）或 `error`

### 資料導入與上傳 Data

- POST `/data/import`
  - Request JSON：
    - **excel_dir**: string（可選）Excel 根目錄；未提供則使用全域組態
  - 行為：背景呼叫離線導入邏輯，掃描目錄並入庫
  - 回應：`{"task_id": string, "status": "queued"}`

- POST `/data/upload`
  - multipart/form-data 表單：
    - **file**: 單一 Excel（.xlsx/.xls）
    - **excel_dir**: string（可選）保存根目錄；缺省時使用全域組態
  - 行為：儲存至 `excel_dir`，隨後觸發目錄導入
  - 回應：`{"task_id": string, "status": "queued", "saved_path": string}`

- POST `/data/upload_many`
  - multipart/form-data 表單：
    - **files**: 多個 Excel 檔
    - **excel_dir**: string（可選）
  - 回應：`{"task_id": string, "status": "queued", "saved_paths": string[]}`

- POST `/data/upload_and_rebuild`
  - multipart/form-data 表單：
    - **file**: 單一 Excel 檔
    - **excel_dir**: string（可選）
    - **policy**: string（可選）嵌入策略：`rebuild` | `build_if_missing` | `load_only`（預設 `rebuild`）
    - **save_path**: string（可選）嵌入保存路徑，預設 `online_inference/embedding.pkl`
    - **doc_dir**: string（可選）Schema 目錄
    - **bge_dir**: string（可選）模型目錄
  - 行為：儲存 → 導入 → 建立/重建嵌入
  - 回應：`{"task_id": string, "status": "queued", "saved_path": string}`

- POST `/data/upload_and_rebuild_many`
  - multipart/form-data 表單：同上，但支援多個 **files**
  - 回應：`{"task_id": string, "status": "queued", "saved_paths": string[]}`

- GET `/data/tasks/{task_id}`
  - 回應：任務狀態；成功時 `result` 可能含 `save_path`、`policy`、`excel_dir`、`doc_dir` 等。

### 向量構建 Embeddings

- POST `/embeddings/build`
  - Request JSON：
    - **doc_dir**: string（可選）
    - **excel_dir**: string（可選）
    - **bge_dir**: string（可選）
    - **save_path**: string（可選，預設 `online_inference/embedding.pkl`）
    - **policy**: string（可選，預設 `rebuild`）
  - 行為：呼叫 `online_inference/embed_index.py` 產生/重建索引
  - 回應：`{"task_id": string, "status": "queued"}`

- GET `/embeddings/tasks/{task_id}`
  - 回應：任務狀態；成功時 `result` 含 `save_path`、`policy`

### 表列表 Tables

- GET `/tables`
  - Query 參數：
    - **doc_dir**: string（可選）
    - **excel_dir**: string（可選）
    - **include_meta**: boolean（預設 false）是否回傳中繼資料
  - 回應：
    - 基本：`{"tables": string[], "count": number}`
    - `include_meta=true` 時：新增 `meta`（與排序對齊），元素含 `table`、`table_name`、`original_filename`、`source_file_hash`

### 問答 Chat

- POST `/chat/ask`
  - Request JSON：
    - **question**: string（必填）
    - **table_id**: string（可選，預設 `auto`）
    - **tables**: string[]（可選）
    - **doc_dir**: string（可選）
    - **excel_dir**: string（可選）
    - **bge_dir**: string（可選）
    - **embedding_policy**: string（可選）
    - **backbone**: string（可選，預設 `qwen2.57b`）
  - 回應：`{"answer": string}`；失敗回傳 500 與 `detail`

## 常用參數總覽

- **excel_dir**（string，可選）
  - 適用：所有上傳/導入相關端點
  - 用途：指定 Excel 保存或掃描的根目錄

- **doc_dir**（string，可選）
  - 適用：向量構建、重建相關（`/embeddings/build`、`/data/upload_and_rebuild*`）
  - 用途：Schema 定義目錄，供索引與表名解析

- **bge_dir**（string，可選）
  - 適用：向量構建、重建相關
  - 用途：BGE 模型檔案所在目錄

- **policy**（string，可選，預設 `rebuild`）
  - 值：`rebuild` | `build_if_missing` | `load_only`
  - 適用：向量構建、重建相關

- **save_path**（string，可選，預設 `online_inference/embedding.pkl`）
  - 適用：向量構建、重建相關
  - 用途：嵌入索引的輸出檔

- **table_id**（string，可選，預設 `auto`）
  - 適用：`/chat/ask`
  - 用途：指定查詢的表；`auto` 由系統自動挑選

- **tables**（string[]，可選）
  - 適用：`/chat/ask`
  - 用途：限制候選表集合

- **embedding_policy**（string，可選）
  - 適用：`/chat/ask`
  - 用途：問答時的嵌入策略（沿用向量構建語意）

- **backbone**（string，可選，預設 `qwen2.57b`）
  - 適用：`/chat/ask`
  - 用途：回答生成所用的模型

