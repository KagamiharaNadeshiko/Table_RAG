import os

# Allow configuring the OpenAI-compatible base URL via environment variable, defaulting to the
# dedicated LLM container service name "ollama" exposed at port 11434 in docker-compose.
# Example: export OLLAMA_BASE_URL=http://ollama:11434
_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")

v3_config = {
    "url": "url for deepseek_v3",
    "model": "deepseek_chat",
    "api_key": "api_key"
}

qwen2_57b_config = {
    # Provide base URL; chat_utils will normalize to /v1/chat/completions when needed
    "url": _OLLAMA_BASE_URL,
    "model": "qwen2.5:7b",
    "api_key": ""
}

qwen3_8b_config = {
    "url": _OLLAMA_BASE_URL,
    "model": "qwen3:8b",
    "api_key": "",
    "no_think": True
}

# 配置您的SQL服务地址（offline部分的Flask服务）
sql_service_url = 'http://localhost:5000/get_tablerag_response'

# 表选择策略配置（内容权重大，表名权重小）
table_selection_config = {
    # α：内容分数权重；β：表名分数权重
    "alpha_content_weight": 0.85,
    "beta_name_weight": 0.15,
    # 每个表聚合内容分数时采用的 top-m chunk（使用 max 聚合）
    "aggregate_top_m": 3,
    # 强内容命中阈值（>= 即视为强命中）；无强命中时走合成排序
    "strong_content_threshold": 0.5,
    # 自动选择时默认返回的相关表数量（含 top1）
    "default_top_k": 3
}

config_mapping = {
    "v3": v3_config,
    "qwen2.57b": qwen2_57b_config,
    "qwen3.8b": qwen3_8b_config,
    # 兼容命名：部分程式與文件使用底線版本
    "qwen3_8b": qwen3_8b_config
}