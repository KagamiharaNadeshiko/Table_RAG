# -*- coding: utf-8 -*-
import re
import json
import time
import os
from .log_service import logger
from .prompt import *
from .handle_requests import get_llm_response
from .common_utils import transfer_name, SCHEMA_DIR, sql_alchemy_helper


def find_actual_schema_file(base_table_name):
    """
    根据基础表名查找实际的schema文件（可能带有哈希后缀）
    
    Args:
        base_table_name (str): 基础表名（如 'financial_report_2024'）
    
    Returns:
        str: 实际的schema文件名，如果找不到则返回None
    """
    if not os.path.exists(SCHEMA_DIR):
        return None
    
    # 查找匹配的文件
    for filename in os.listdir(SCHEMA_DIR):
        if filename.endswith('.json'):
            # 检查文件名是否以基础表名开头
            if filename.startswith(base_table_name + '_') or filename == base_table_name + '.json':
                return filename
    
    return None


def extract_sql_statement(resp_content):  
    """
    从响应内容中提取SQL语句。
    
    Args:
        resp_content (str): 响应内容，包含SQL语句。
    
    Returns:
        str: 提取的SQL语句。
    """
    if not isinstance(resp_content, str) or not resp_content:
        logger.error(f"LLM response content is empty or not a string: {resp_content}")
        return None

    # 使用正则表达式匹配SQL语句
    match = re.search(r'```sql([\s\S]*?)```', resp_content, re.DOTALL)
    if match:
        matched_text = match.group(1).strip()
        sql_text = re.sub(r'\s+', ' ', matched_text)  # 压缩空白字符
        return sql_text
    else:
        logger.error(f"No SQL statement found in the response content. Response content: {resp_content}")
        return None
    

def process_tablerag_request(table_name_list, query):
    """
    Process the request for TableRAG.
    
    Args:
        table_name_list (list): List of table names related to the query.
        query (str): The query string to be processed.
    
    Returns:
        str: A mock response for demonstration purposes.
    """
    # Here you would implement the actual logic to process the request
    # For demonstration, we will just return a mock response

    schema_list = []
    for table_name in table_name_list:
        # 转换表名
        converted_table_name = transfer_name(table_name)
        
        # 查找实际的schema文件
        actual_filename = find_actual_schema_file(converted_table_name)
        
        if actual_filename is None:
            logger.error(f"Schema file not found for table: {converted_table_name}")
            continue
            
        schema_path = os.path.join(SCHEMA_DIR, actual_filename)
        
        try:
            schema_dict = json.load(open(schema_path, 'r', encoding='utf-8'))
            schema_list.append(schema_dict)
        except Exception as e:
            logger.error(f"Failed to load schema file {schema_path}: {e}")
            continue
    
    if not schema_list:
        logger.error("No valid schema files found")
        return {
            'error': 'No valid schema files found',
            'query': query
        }
    
    nl2sql_prompt = NL2SQL_USER_PROMPT.format(
        schema_list=json.dumps(schema_list, ensure_ascii=False),
        user_query=query
    )

    nl2sql_start_time = time.time()
    resp_content = get_llm_response(
        system_prompt=NL2SQL_SYSTEM_PROMPT,
        user_prompt=nl2sql_prompt
    )
    nl2sql_end_time = time.time()
    nl2sql_time_cusumed = nl2sql_end_time - nl2sql_start_time

    sql_str = extract_sql_statement(resp_content)
    if not sql_str:
        return {
            'error': 'Failed to extract SQL from LLM response',
            'query': query,
            'nl2sql_response': resp_content
        }

    sql_excution_start_time = time.time()
    try:
        sql_excution_result = sql_alchemy_helper.fetchall(sql_str)
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        sql_excution_result = f"SQL execution failed: {str(e)}"
        
    sql_excution_end_time = time.time()
    sql_excution_time_cusumed = sql_excution_end_time - sql_excution_start_time

    time_consumed_str = f"NL2SQL time: {nl2sql_time_cusumed:.2f}s, SQL execution time: {sql_excution_time_cusumed:.2f}s"

    res_dict = {
        'query': query,
        'nl2sql_prompt': nl2sql_prompt,
        'nl2sql_response': resp_content,
        'sql_str': sql_str,
        'sql_execution_result': sql_excution_result,
        'time_consumed': time_consumed_str
    }
    return res_dict
    

        
