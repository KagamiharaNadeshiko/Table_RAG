import json
import requests
from openai import OpenAI
import logging
from functools import wraps
from typing import Dict, Any, Optional
import os
import hashlib
import time
from config import *
import httpx

def init_logger(name='my_logger', level=logging.DEBUG, log_file='app.log') :
    """
    Initialize a logger with console and file handlers.

    Args:
        level(int): logging level(DEBUG, INFO, WARINING...)
    """
    logger = logging.getLogger(name)

    if logger.hasHandlers() :
        logger.handlers.clear()

    logger.setLevel(level=level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


def get_chat_result(
    messages: object, 
    tools: object = None,
    tool_choice: object = None,
    llm_config: Dict = None
    ) :
    """
    Get LLM generation result of different API backend, e.g. gpt-4o, ollama.
    """
    # Check if it's Ollama API (no api_key needed)
    # We treat any endpoint that clearly targets an Ollama server or already points to
    # the full chat-completions path as a direct HTTP endpoint (not OpenAI SDK base_url).
    url_value = llm_config.get('url', '') or ''
    is_ollama = ('ollama' in url_value) or (':11434' in url_value)
    is_full_chat_path = url_value.rstrip('/').endswith('/v1/chat/completions')
    if is_ollama or is_full_chat_path:
        # Normalize service URL: if it's just base host, append the chat path
        base = url_value.rstrip('/')
        if base.endswith('/v1'):
            service_url = f"{base}/chat/completions"
        elif base.endswith(':11434') or base.endswith(':11434/v1') or ('ollama' in base and not is_full_chat_path):
            # Append missing /v1/chat/completions if needed
            if base.endswith(':11434'):
                service_url = f"{base}/v1/chat/completions"
            elif base.endswith(':11434/v1'):
                service_url = f"{base}/chat/completions"
            else:
                service_url = base if is_full_chat_path else f"{base}/v1/chat/completions"
        else:
            service_url = base
        payload = {
            "model": llm_config.get('model', ''),
            "messages": messages,
            "temperature": 0.1,
            "stream": False
        }
        
        # Add no_think mode if specified in config
        if llm_config.get('no_think', False):
            payload["options"] = {
                "num_ctx": 4096,
                "num_predict": 2048,
                "stop": ["<|im_start|>", "<|im_end|>", "<|endoftext|>"],
                "temperature": 0.1,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "num_gpu": 1,
                "num_thread": 8,
                "no_think": True
            }
        
        if tools:
            payload["tools"] = tools
            
        headers = {
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                service_url,
                json=payload,
                headers=headers,
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            return (data.get('choices') or [{}])[0].get('message')
        except Exception as e:
            print(f"Ollama API request failed: {e}")
            raise e
    
    # For other APIs (OpenAI compatible)
    # For OpenAI-compatible providers, the base_url should be the API base (e.g. https://host/v1)
    client = OpenAI(
        api_key=llm_config.get('api_key', ''),
        base_url=llm_config.get('url', '')
    )
    try :
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=llm_config.get('model', 'gpt-4o'),
            tools=tools,
            temperature=0.1
        )
        return chat_completion.choices[0].message
    except Exception as e:
        print(f"OpenAI API request failed: {e}")
        # Fallback to direct HTTP request
        service_url = llm_config.get('url', '')
        payload = {
            "model": llm_config.get('model', ''),
            "messages": messages,
            "temperature": 0.1,
            "tools": tools
        }
        headers = {
            "Content-Type": "application/json",
        }
        if llm_config.get('api_key'):
            headers["Authorization"] = f"Bearer {llm_config.get('api_key')}"
            
        response = requests.post(
            service_url,
            json=payload,
            headers=headers,
            timeout=300
        )
        response.raise_for_status()
        return json.loads(response.text)['choices'][0]["message"]
