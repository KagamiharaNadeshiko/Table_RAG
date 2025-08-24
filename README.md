# TableRAG: 



**核心特點：**
- **語義檢索**: 使用BGE-M3模型進行智能文檔檢索
- **SQL生成**: 自然語言轉SQL查詢
- **多跳推理**: 支持複雜問題的逐步推理
- **混合檢索**: 結合文本檢索和SQL執行
- **交互式使用**: 支持命令行和Web界面

## 系統架構

TableRAG包含兩個主要階段：

### 1. **離線階段** (Offline Phase)
- 數據庫建構和數據攝取
- Schema生成和存儲
- 向量索引建立

### 2. **線上階段** (Online Phase)  
- 語義檢索和重排序
- SQL生成和執行
- 多跳推理和答案生成

---

## 快速部署指南

### 前置要求

```bash
# 1. 創建Python環境
conda create -n tablerag python=3.10
conda activate tablerag

# 2. 安裝依賴
cd TableRAG
pip install -r requirements.txt

# 3. 下載BGE模型 (可選，首次運行會自動下載)
# BGE-M3: 用於語義檢索
# BGE-Reranker-V2-M3: 用於重排序
```

### 步驟1: 設置MySQL數據庫

```bash
# 1. 下載並安裝MySQL 8.0.24
# 訪問: https://downloads.mysql.com/archives/community/

# 2. 創建數據庫
mysql -u root -p
CREATE DATABASE TableRAG;
```

### 步驟2: 離線數據攝取

```bash
# 1. 配置數據庫連接
 offline_data_ingestion_and_query_interface/config/database_config.json

{
    "host": "localhost",
    "port": 3306,
    "user": "your_username",
    "password": "your_password",
    "database": "TableRAG"
}

# 2. 準備數據文件
# 準備表格到指定目錄
offline_data_ingestion_and_query_interface/dataset/hybridqa/dev_excel/

# 3. 執行數據攝取
cd offline_data_ingestion_and_query_interface/src/
python data_persistent.py
```

**離線階段功能：**
- 自動推斷數據類型
- 生成JSON Schema文件
- 將Excel數據導入MySQL
- 創建向量索引

### 步驟3: 啟動SQL查詢服務

```bash
# 1. 配置LLM API
vim offline_data_ingestion_and_query_interface/src/handle_requests.py

# 設置您的LLM API配置
model_request_config = {
    "url": "your_llm_api_url",
    "api_key": "your_api_key",
    "model": "your_model_name"
}

# 2. 啟動服務
python interface.py
# 服務將在 http://localhost:5000 啟動
```

### 步驟4: 配置線上推理

```bash
# 1. 配置LLM和SQL服務
vim online_inference/config.py

# 設置LLM配置
v3_config = {
    "url": "your_llm_api_url",
    "model": "your_model_name", 
    "api_key": "your_api_key"
}

# 設置SQL服務URL
sql_service_url = 'http://localhost:5000/get_tablerag_response'

# 2. 準備數據目錄
mkdir -p online_inference/data/schema
mkdir -p online_inference/data/dataset/dev_excel
mkdir -p online_inference/bge_models

# 3. 複製必要文件
cp offline_data_ingestion_and_query_interface/data/schema/* online_inference/data/schema/
cp offline_data_ingestion_and_query_interface/dataset/hybridqa/dev_excel/* online_inference/data/dataset/dev_excel/
```

---

## 使用方式

### 方式1: 批量實驗 (推薦用於評估)

```bash
cd online_inference

# 運行批量實驗（支持智能表格選擇）
python main.py \
    --backbone gpt-4o \
    --data_file_path ./data/sample_auto_queries.json \
    --doc_dir ./data/schema \
    --excel_dir ./data/dataset/dev_excel \
    --bge_dir ./bge_models \
    --save_file_path ./results/output.json \
    --max_iter 5 \
    --rerun False
```

**智能表格選擇功能：**
- **自動表格選擇**: 設置 `"table_id": "auto"` 或省略 `table_id` 字段
- **語義匹配**: 根據問題內容自動選擇最相關的表格
- **多表格支持**: 支持跨表格的聯合查詢
- **向後兼容**: 仍支持手動指定 `table_id`

### 方式2: 命令行交互 (用於測試)

```bash
cd online_inference

# 啟動命令行交互界面
python interactive_chat.py \
    --backbone gpt-4o \
    --doc_dir ./data/schema \
    --excel_dir ./data/dataset/dev_excel \
    --bge_dir ./bge_models
```

**交互功能：**
- **智能表格選擇** - 無需指定表格名稱
- **自然語言問答** - 直接問問題即可
- **查看推理過程** - 詳細的分析步驟
- **詳細日誌記錄** - 完整的執行日誌
- **內置幫助系統** - 輸入 `help` 查看幫助
- **表格列表** - 輸入 `tables` 查看可用表格

---

## 配置詳解

### LLM模型配置

```python
# online_inference/config.py

# OpenAI GPT-4o
gpt4o_config = {
    "url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "api_key": "your_openai_key"
}

# 通義千問2.5 7B (本地)
qwen2_57b_config = {
    "url": "http://localhost:11434/v1/chat/completions",
    "model": "qwen2.5:7b",
    "api_key": ""
}

# DeepSeek V3
v3_config = {
    "url": "your_deepseek_url",
    "model": "deepseek_chat",
    "api_key": "your_deepseek_key"
}
```

### 數據格式

**測試問題文件格式 (JSONL):**

**傳統方式（需要指定表格）：**
```json
{"question": "這個表格中有多少行數據？", "table_id": "sample_table"}
{"question": "找出銷售額最高的產品", "table_id": "sales_table"}
{"question": "計算平均價格", "table_id": "product_table"}
```

**智能表格選擇方式（推薦）：**
```json
{"question": "銷售額最高的產品是什麼？", "table_id": "auto"}
{"question": "計算平均工資", "table_id": "auto"}
{"question": "找出年齡大於30歲的員工"}
{"question": "按銷售額排序顯示前5名"}
```

**Schema文件格式:**
```json
{
    "table_name": "sample_table",
    "columns": [
        ["id", "INT", "sample values:['1', '2', '3']"],
        ["name", "VARCHAR(255)", "sample values:['John', 'Jane', 'Bob']"],
        ["price", "FLOAT", "sample values:['100.0', '200.0', '150.0']"]
    ]
}
```

---

## 支持的問答類型

### 1. 基礎數據查詢
```
Q: "這個表格中有多少行數據？"
A: "根據查詢結果，該表格共有1,234行數據。"
```

### 2. 統計分析
```
Q: "計算平均銷售額"
A: "平均銷售額為 $15,678.90"
```

### 3. 條件篩選
```
Q: "找出銷售額大於10000的產品"
A: "符合條件的產品有：[產品列表]"
```

### 4. 排序查詢
```
Q: "按銷售額降序排列前5名"
A: "銷售額前5名：1. 產品A: $50,000, 2. 產品B: $45,000..."
```

### 5. 複雜推理
```
Q: "哪個部門的平均工資最高？"
A: "通過分析各部門數據，技術部的平均工資最高，為$8,500/月。"
```

---

## 技術架構詳解

### 語義檢索流程
1. **文本嵌入**: 使用BGE-M3將問題轉換為向量
2. **向量檢索**: 在FAISS索引中搜索相似文檔
3. **重排序**: 使用BGE-Reranker精確排序
4. **文檔融合**: 整合相關文檔內容

### SQL生成流程
1. **Schema檢索**: 找到相關表格結構
2. **NL2SQL**: 自然語言轉SQL查詢
3. **SQL執行**: 在MySQL中執行查詢
4. **結果整合**: 格式化查詢結果

### 多跳推理流程
1. **問題分解**: 將複雜問題分解為子問題
2. **迭代推理**: 最多5次迭代推理
3. **工具調用**: 使用solve_subquery工具
4. **答案生成**: 整合所有子問題答案

