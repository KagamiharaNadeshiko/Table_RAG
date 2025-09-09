# TableRAG API 介面說明（apiserve）

本文件詳細說明 `apiserve` 模組所提供的 FastAPI 介面、請求參數、執行邏輯與回應格式，並補充全域設定合併規則與背景任務查詢方式。

---

### 全域設計與共同概念

- **應用版本**: 0.1.0（見 `apiserve/main.py` 與 `/health`）
- **路由前綴**：
  - `cleanup`、`data`、`embeddings`、`tables`、`chat` 分別對應各自的 router
  - `health` 無額外前綴（直接 `/health`）
- **背景任務隊列**：所有需要較長時間執行的作業（匯入、清理、建置向量）都會透過 `InMemoryTaskQueue` 非同步執行，並回傳 `task_id` 讓客戶端查詢狀態。
  - 任務狀態：`queued` | `running` | `succeeded` | `failed`
  - 任務查詢回應格式：
    ```json
    {
      "task_id": "<uuid>",
      "status": "queued|running|succeeded|failed",
      "result": <任務回傳結果或 null>,
      "error": <錯誤訊息或 null>,
      "created_at": <float 秒>,
      "started_at": <float 秒或 null>,
      "ended_at": <float 秒或 null>
    }
    ```
- **全域設定合併（merge_config）**：
  - 來源依序：`DEFAULTS`（內建） + `apiserve/config.json`（若存在） + 本次請求中的欄位（非 None）
  - 內建 `DEFAULTS`：
    - `doc_dir`: `offline_data_ingestion_and_query_interface/data/schema`
    - `excel_dir`: `offline_data_ingestion_and_query_interface/dataset/dev_excel`
    - `bge_dir`: `online_inference/bge_models`
    - `embedding_save_path`: `online_inference/embedding.pkl`
    - `embedding_policy`: `build_if_missing`
    - `backbone`: `qwen2.57b`

---

## 健康檢查

### GET /health

- **說明**：服務健康檢查與版本資訊。
- **請求參數**：無
- **回應**：
  
  ```json
  { "status": "ok", "version": "0.1.0" }
  ```

---

## 清理（Cleanup）

路由前綴：`/cleanup`

### POST /cleanup

- **說明**：呼叫離線模組 `offline_data_ingestion_and_query_interface.src.cleanup.run_cleanup` 進行清理作業（依 Excel 檔名目標移除資料/結構）。非同步執行，回傳 `task_id`。
- **Request Body**（JSON）：
  - `targets: string[]`（必填）：目標 Excel 檔名（或邏輯識別）
  - `yes: boolean`（選填，預設 true）：是否無問答確認直接執行
  - `dry_run: boolean`（選填，預設 false）：僅試跑不落實變更
  - `remove_excel: boolean | null`（選填，預設 true）：預留擴充（目前不在任務內部使用）
- **回應**：
  
  ```json
  { "task_id": "<uuid>", "status": "queued" }
  ```

### GET /cleanup/tasks/{task_id}

- **說明**：查詢清理任務狀態與結果。
- **回應**：見「背景任務隊列」的通用回應格式。

---

## 資料（Data）

路由前綴：`/data`

### POST /data/import

- **說明**：以離線模組 `parse_excel_file_and_insert_to_db(excel_dir)` 將指定資料夾中的 Excel 匯入 DB。非同步執行。
- **Request Body**（JSON）：
  - `excel_dir: string | null`：Excel 來源根目錄。若未提供，使用合併後設定中的 `excel_dir`（見全域設定合併）。
- **回應**：
  
  ```json
  { "task_id": "<uuid>", "status": "queued" }
  ```

### GET /data/tasks/{task_id}

- **說明**：查詢匯入任務狀態。
- **回應**：通用任務格式。

### POST /data/upload

- **說明**：上傳單一 Excel 至伺服器端的 `excel_dir` 目錄，隨後提交匯入任務。
- **表單參數（multipart/form-data）**：
  - `file`（必填）：Excel 檔案（僅支援 `.xlsx` 或 `.xls`）
  - `excel_dir: string | null`：覆寫目標根目錄。若未提供，使用合併後設定。
- **回應**：
  
  ```json
  { "task_id": "<uuid>", "status": "queued", "saved_path": "<server/path>" }
  ```

### POST /data/upload_many

- **說明**：批次上傳多個 Excel 檔案至伺服器端 `excel_dir`，隨後提交一次匯入任務（針對整個目錄）。
- **表單參數（multipart/form-data）**：
  - `files`（必填，重複欄位）：多個 Excel 檔案
  - `excel_dir: string | null`：覆寫目標根目錄。未給則用設定。
- **回應**：
  
  ```json
  { "task_id": "<uuid>", "status": "queued", "saved_paths": ["<server/path>", ...] }
  ```

### POST /data/upload_and_rebuild

- **說明**：上傳單一 Excel → 先匯入 DB → 再呼叫向量建置（`online_inference.embed_index.main`）。兩步驟在同一個背景任務中串行執行。
- **表單參數（multipart/form-data）**：
  - `file`（必填）：Excel 檔案
  - `excel_dir: string | null`：匯入根目錄
  - `policy: string | null`：向量建置策略（`rebuild` | `build_if_missing` | `load_only`）。若未提供，採合併設定或預設 `rebuild`（此路由內部）。
  - `save_path: string | null`：向量儲存路徑。若未提供，優先取合併設定 `embedding_save_path`，否則預設 `online_inference/embedding.pkl`。
  - `doc_dir: string | null`：結構化 schema 目錄
  - `bge_dir: string | null`：BGE 模型目錄
- **背景任務內部步驟**：
  1. 呼叫 `parse_excel_file_and_insert_to_db(final_excel_dir)` 將 `excel_dir` 下資料全部匯入。
  2. 組合 `argv = [--doc_dir, --excel_dir, --bge_dir, --save_path, --policy]` 後呼叫 `embed_index.main()` 進行嵌入建置/載入。
- **回應**：
  
  ```json
  { "task_id": "<uuid>", "status": "queued", "saved_path": "<server/path>" }
  ```

### POST /data/upload_and_rebuild_many

- **說明**：批次上傳多個 Excel，然後在單一背景任務中：先匯入整個 `excel_dir`，再建置/載入向量。
- **表單參數（multipart/form-data）**：
  - `files`（必填，重複欄位）
  - 其餘與 `/data/upload_and_rebuild` 相同：`excel_dir`、`policy`、`save_path`、`doc_dir`、`bge_dir`
- **回應**：
  
  ```json
  { "task_id": "<uuid>", "status": "queued", "saved_paths": ["<server/path>", ...] }
  ```

---

## 向量嵌入（Embeddings）

路由前綴：`/embeddings`

### POST /embeddings/build

- **說明**：直接呼叫 `online_inference.embed_index.main` 進行向量建置/載入，非同步執行。
- **Request Body**（JSON）：
  - `doc_dir: string | null`
  - `excel_dir: string | null`
  - `bge_dir: string | null`
  - `save_path: string | null`：若不提供，優先採用合併設定的 `embedding_save_path`，否則預設 `online_inference/embedding.pkl`
  - `policy: string | null`：`rebuild` | `build_if_missing` | `load_only`
- **回應**：
  - 提交任務：
  
  ```json
  { "task_id": "<uuid>", "status": "queued" }
  ```
  - 任務成功的 `result` 內容（於任務查詢回傳中）：
  
  ```json
  { "save_path": "...", "policy": "..." }
  ```

### GET /embeddings/tasks/{task_id}

- **說明**：查詢嵌入建置/載入任務狀態。
- **回應**：通用任務格式。

---

## 表格（Tables）

路由前綴：`/tables`

### GET /tables

- **說明**：列出 `doc_dir` 目錄下所有 `.json` schema 檔名（去除副檔名），並可選擇輸出每個表格的原始檔名等 metadata。
- **查詢參數（Query）**：
  - `doc_dir: string | null`：覆寫預設 schema 目錄（否則使用合併設定）
  - `excel_dir: string | null`：預留；目前僅參與合併設定，不影響此路由邏輯
  - `include_meta: boolean`（預設 false）：是否同時回傳每個表格對應 metadata（`table_name`、`original_filename`、`source_file_hash`）。
- **回應**：
  - `include_meta=false`：
    
    ```json
    { "tables": ["table_a", "table_b", ...], "count": 2 }
    ```
  - `include_meta=true`：
    
    ```json
    {
      "tables": ["table_a", ...],
      "count": 1,
      "meta": [
        {
          "table": "table_a",
          "table_name": "...",
          "original_filename": "...xlsx",
          "source_file_hash": "..."
        }
      ]
    }
    ```

---

## 對話（Chat）

路由前綴：`/chat`

### POST /chat/ask

- **說明**：一次性問答。將請求參數合併為 `Args` 後，臨時切換工作目錄至 `online_inference`，動態匯入並呼叫 `interactive_chat(args)`，捕捉其 `stdout` 最後一行非空文本作為回答。
- **Request Body**（JSON）：
  - `question: string`（必填）：提問內容
  - `table_id: string | null`（預設 `auto`）：指定表格 ID 或自動選擇
  - `tables: string[] | null`：可選表格清單（交由 `interactive_chat` 使用）
  - `doc_dir: string | null`：schema 目錄（會轉為專案根目錄下的絕對路徑）
  - `excel_dir: string | null`：Excel 目錄（同上）
  - `bge_dir: string | null`：BGE 模型目錄（同上）
  - `embedding_policy: string | null`：向量策略（傳遞給 `interactive_chat`）
  - `backbone: string | null`：LLM 背骨（預設來自合併設定 `backbone`）
- **邏輯重點**：
  - 為相容 `online_inference` 內部的相對匯入與檔案尋址，會：
    1. 將 `online_inference` 臨時加入 `sys.path`
    2. `chdir` 到 `online_inference`
    3. 執行完畢後復原現場（`sys.path` 與工作目錄）
  - 會將所有路徑參數標準化為專案根目錄下的絕對路徑，再交由 `interactive_chat` 使用。
- **回應**：
  
  ```json
  { "answer": "<最終答案文本（來自 stdout 最後一行）>" }
  ```

---

## 典型使用情境與範例

> 以下僅示意，實際參數請依部署路徑調整。

### 1) 健康檢查

```bash
curl http://127.0.0.1:8000/health
```

### 2) 列出表格（含原始檔名）

```bash
curl "http://127.0.0.1:8000/tables?include_meta=true"
```

### 3) 匯入 Excel 資料夾

```bash
curl -X POST http://127.0.0.1:8000/data/import \
  -H "Content-Type: application/json" \
  -d '{"excel_dir": "offline_data_ingestion_and_query_interface/dataset/dev_excel"}'
```

### 4) 單檔上傳並匯入

```bash
curl -X POST http://127.0.0.1:8000/data/upload \
  -F "excel_dir=offline_data_ingestion_and_query_interface/dataset/dev_excel" \
  -F "file=@/path/to/sample.xlsx"
```

### 5) 批次上傳並匯入

```bash
curl -X POST http://127.0.0.1:8000/data/upload_many \
  -F "excel_dir=offline_data_ingestion_and_query_interface/dataset/dev_excel" \
  -F "files=@/path/to/a.xlsx" -F "files=@/path/to/b.xlsx"
```

### 6) 上傳並重建向量

```bash
curl -X POST http://127.0.0.1:8000/data/upload_and_rebuild \
  -F "file=@/path/to/sample.xlsx" \
  -F "excel_dir=offline_data_ingestion_and_query_interface/dataset/dev_excel" \
  -F "policy=rebuild" -F "doc_dir=offline_data_ingestion_and_query_interface/data/schema" \
  -F "bge_dir=online_inference/bge_models" -F "save_path=online_inference/embedding.pkl"
```

### 7) 建置/載入向量（不含上傳）

```bash
curl -X POST http://127.0.0.1:8000/embeddings/build \
  -H "Content-Type: application/json" \
  -d '{
        "doc_dir": "offline_data_ingestion_and_query_interface/data/schema",
        "excel_dir": "offline_data_ingestion_and_query_interface/dataset/dev_excel",
        "bge_dir": "online_inference/bge_models",
        "policy": "build_if_missing",
        "save_path": "online_inference/embedding.pkl"
      }'
```

### 8) 問答

```bash
curl -X POST http://127.0.0.1:8000/chat/ask \
  -H "Content-Type: application/json" \
  -d '{
        "question": "請根據表格回答...",
        "table_id": "auto",
        "embedding_policy": "build_if_missing"
      }'
```

### 9) 任務狀態查詢（以 embeddings 為例）

```bash
curl http://127.0.0.1:8000/embeddings/tasks/<task_id>
```

---

## 參考：CLI 工具（呼叫 API 的指令稿）

- `apiserve/cli/cleanup.py`：提交清理作業並可 `--wait` 等待完成
- `apiserve/cli/embeddings.py`：提交建置/載入嵌入的任務並可 `--wait`
- `apiserve/cli/import_data.py`：提交匯入任務並可 `--wait`
- `apiserve/cli/tables.py`：列出表格，支援 `--include-meta`、`--pretty`、`--filenames-only`
- `apiserve/cli/multi_upload.py`：多檔上傳，選配 `--rebuild` 一次完成上傳+重建
- `apiserve/cli/chat.py`：一次性問答

---

## 錯誤處理與邊界

- 任務查無時（查詢 `/.../tasks/{task_id}`）：回傳 404 與 `{"detail": "task not found"}`
- 上傳檔案副檔名限制：僅允許 `.xlsx` 或 `.xls`，否則回 400
- 必要路徑缺失（例如未能解析到 `excel_dir`）：回 400 並提示
- `/chat/ask` 內部執行 `interactive_chat` 若拋出例外，會捕捉 traceback 並回 500

---


