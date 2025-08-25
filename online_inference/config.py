v3_config = {
    "url": "url for deepseek_v3",
    "model": "deepseek_chat",
    "api_key": "api_key"
}

qwen2_57b_config = {
    "url": "http://localhost:11434/v1/chat/completions",
    "model": "qwen2.5:7b",
    "api_key": ""
}

# 配置您的SQL服务地址（offline部分的Flask服务）
sql_service_url = 'http://localhost:5000/get_tablerag_response'

config_mapping = {
    "v3": v3_config,
    "qwen2.57b": qwen2_57b_config
}