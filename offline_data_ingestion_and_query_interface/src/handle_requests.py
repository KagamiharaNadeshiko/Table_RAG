import requests
import time
import json
import os
from typing import Optional, Dict, Any

# Load model configuration from config file
def load_model_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'llm_config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Warning: LLM config file not found at {config_path}, using default config")
        return {
            "default_model": "qwen2.57b",
            "models": {
                "qwen2.57b": {
                    "endpoint": "http://localhost:11434/v1/chat/completions",
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "model": "qwen2.5:7b",
                    "temperature": 0.01
                }
            }
        }

# Load configuration
llm_config = load_model_config()
model_request_config = llm_config["models"]

def call_llm_api(
    endpoint: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    initial_retry_delay: float = 1.0
) -> Optional[Dict[str, Any]]:
    """
    调用大模型推理接口，包含异常捕获和指数退避重试机制
    
    :param endpoint: API端点URL
    :param payload: 请求体数据
    :param headers: 请求头(可选)
    :param max_retries: 最大重试次数
    :param initial_retry_delay: 初始重试延迟(秒)
    :return: 响应数据或None(失败时)
    """
    retry_delay = initial_retry_delay
    headers = headers or {"Content-Type": "application/json"}
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            resp_json_body = response.json()
            resp_content = resp_json_body['choices'][0]['message']['content']
            return resp_content
        except (requests.exceptions.RequestException, 
                requests.exceptions.JSONDecodeError, 
                json.JSONDecodeError,
                ValueError, 
                KeyError,
                IndexError,
                TypeError) as e:
            if attempt == max_retries:
                print(f"Request failed after {max_retries} retries. Error: {str(e)}")
                return None
            
            print(f"Attempt {attempt + 1} failed. Retrying in {retry_delay:.1f}s... Error: {str(e)}")
            time.sleep(retry_delay)
            retry_delay *= 2  # 指数退避
            
    return None


def get_llm_response(
    system_prompt: Optional[str],
    user_prompt: str,
    model: str = None,
) -> Optional[str]:
    if model is None:
        model = llm_config.get("default_model", "qwen2.57b")
    
    model_config = model_request_config.get(model)
    if not model_config:
        raise ValueError(f"Model '{model}' is not supported.")
    model_endpoint = model_config["endpoint"]
    model_headers = model_config["headers"]
    model_name = model_config["model"]
    temperature = model_config.get("temperature", 0.01)
    no_think = model_config.get("no_think", False)

    payload={
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt} if system_prompt else {},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature
    }
    
    # 添加no_think参数到payload中
    if no_think:
        payload["no_think"] = True

    resp_content = call_llm_api(
        endpoint=model_endpoint,
        payload=payload,
        headers=model_headers
    )
    return resp_content


if __name__ == "__main__":
    # Example usage
    system_prompt = "You are a helpful assistant."
    user_prompt = "What is the capital of France?"
    model = "qwen2.57b"

    response = get_llm_response(system_prompt, user_prompt, model)
    if response:
        print("LLM Response:", response)
    else:
        print("Failed to get a response from the LLM.")