## TableRAG - 快速啟動指南

面向本專案的最小可用啟動說明。

### 環境需求
- **Python**: 3.11
- **MySQL**: 可存取的實例（本機或遠端）
- **作業系統**: Windows / macOS / Linux

### 1) 建立並啟用 Conda 環境
```powershell
# 於專案根目錄
conda create -n tablerag python=3.11 -y
conda activate tablerag
```

### 2) 安裝相依套件
```powershell
pip install -U pip setuptools wheel
pip install -r requirements.txt
```

### 3) 設定資料庫與 LLM
需要的設定檔：
- `offline_data_ingestion_and_query_interface/config/database_config.json`
- `offline_data_ingestion_and_query_interface/config/llm_config.json`

`database_config.json` 範例：
```json
{
  "host": "127.0.0.1",
  "port": 3306,
  "user": "root",
  "password": "your_password",
  "database": "mysql"
}
```

若存在 `apiserve/config/llm_config.json`，亦可依需求調整。

`llm_config.json` 範例：
```json
{
  "default_model": "qwen2.57b",
  "models": {
    "deepseek-v3": {
      "endpoint": "https://api.deepseek.com/v1/chat/completions",
      "headers": { "Authorization": "Bearer sk-xxx", "Content-Type": "application/json" },
      "model": "deepseek-v3",
      "temperature": 0.01
    },
    "qwen2.57b": {
      "endpoint": "http://localhost:11434/v1/chat/completions",
      "headers": { "Content-Type": "application/json" },
      "model": "qwen2.5:7b",
      "temperature": 0.01
    },
    "qwen3.8b": {
      "endpoint": "http://localhost:11434/v1/chat/completions",
      "headers": { "Content-Type": "application/json" },
      "model": "qwen3:8b",
      "temperature": 0.01,
      "no_think": true
    }
  }
}
```

說明：
- **default_model**: 啟動/預設使用的模型鍵名（需於 `models` 中存在）。
- **endpoint**: OpenAI 相容介面或本機 Ollama Chat Completions 位址（如 `http://localhost:11434/v1/chat/completions`）。
- **headers**: 若為雲端服務，通常需 `Authorization: Bearer <API_KEY>`。
- **model**: 具體模型名稱（如 `qwen2.5:7b`、`deepseek-v3`）。
- **temperature**: 取樣溫度。
- **no_think**: 部分本機後端的可選參數。

生效範圍：
- MySQL 連線讀取自 `offline_data_ingestion_and_query_interface/config/database_config.json`（由 `src/sql_alchemy_helper.py` 使用）。
- LLM 設定讀取自 `offline_data_ingestion_and_query_interface/config/llm_config.json`（由 `src/handle_requests.py` 使用）。
- Web/FastAPI 可選覆蓋：若存在 `apiserve/config/llm_config.json`，`start_services.py` 會嘗試讀取用於 Web 層。

修改後請重新啟動：
```powershell
python start_services.py
```

### 4) 一鍵啟動服務
```powershell
python start_services.py
```
此腳本將：
- 檢查必要相依與設定檔
- 啟動以下服務並輸出即時日誌
  - Flask SQL 服務: `http://localhost:5000`
  - FastAPI Web 服務: `http://localhost:8000`
- 詳細日誌寫入 `logs/startup_*.log`

### 5) 驗證
- Web 介面: `http://localhost:8000`
- API 文件: `http://localhost:8000/docs`
- 健康檢查: `http://localhost:8000/health`

### BGE 模型下載與放置
為避免將大型權重提交到 Git，`online_inference/bge_models/` 已被忽略。請依下列方式下載並放置：

```powershell
# 建議使用 huggingface-cli（可從 pip 安裝）
pip install -U "huggingface_hub[cli]"

# 建立模型目錄（如 bge-m3 與 reranker）
mkdir -Force online_inference\bge_models\bge-m3
mkdir -Force online_inference\bge_models\bge-reranker-v2-m3

# 下載 BGE-M3（向量與多語嵌入）
huggingface-cli download BAAI/bge-m3 --local-dir online_inference/bge_models/bge-m3 --local-dir-use-symlinks False

# 下載 BGE Reranker v2 M3（重排序模型）
huggingface-cli download BAAI/bge-reranker-v2-m3 --local-dir online_inference/bge_models/bge-reranker-v2-m3 --local-dir-use-symlinks False
```

若網路環境無法直連 Hugging Face，可先離線下載後手動拷貝到 `online_inference/bge_models/` 對應資料夾。

### 停止服務
於執行視窗按下 `Ctrl + C` 可優雅停止所有服務。

### 常見問題排查
- **缺少相依**: 再次執行 `pip install -r requirements.txt`。
- **連接埠被占用**: 確保 5000 / 8000 可用，或於 `start_services.py` 中調整連接埠。
- **MySQL 連線失敗**: 檢查 `database_config.json` 中的連線資訊，確認 MySQL 運行且可達。
- **設定檔驗證失敗**: 確保上述 JSON 檔案存在且為合法 JSON。
- **日誌位置**: 查看 `logs/` 與根目錄 `app.log` 以取得更多細節。

### 說明
- SQL 服務透過設定 `FLASK_APP=interface:app`，工作目錄為 `offline_data_ingestion_and_query_interface/src`。
- Web 服務入口為 `apiserve.main:app`（使用 `uvicorn` 啟動）。
