import re
import json
import hashlib
import os
from sql_alchemy_helper import SQL_Alchemy_Helper

# 获取项目根目录路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEMA_DIR = os.path.join(PROJECT_ROOT, 'data', 'schema')
DATABASE_CONFIG_DIR = os.path.join(PROJECT_ROOT, 'config', 'database_config.json')

database_config = json.load(open(DATABASE_CONFIG_DIR, 'r', encoding='utf-8'))
sql_alchemy_helper = SQL_Alchemy_Helper(database_config)


def transfer_name(original_name, file_content_hash=None):
    """
    转换文件名为有效的表名，确保唯一性
    
    Args:
        original_name: 原始文件名
        file_content_hash: 文件内容哈希值，用于确保唯一性
    
    Returns:
        唯一的表名
    """
    # 确保输入是字符串类型
    if not isinstance(original_name, str):
        original_name = str(original_name)
    
    # 去除扩展名
    name = original_name.split('.')[0]
    
    # 尝试保留中文信息，将中文转换为拼音或保留关键信息
    # 这里我们保留一些关键信息，比如年份、公司名等
    chinese_patterns = {
        '财报': 'financial_report',
        '财务': 'financial',
        '数据': 'data',
        '资料': 'data',
        'QA': 'qa',
        '问答': 'qa'
    }
    
    # 替换中文关键词
    for chinese, english in chinese_patterns.items():
        name = name.replace(chinese, english)
    
    # 提取年份信息
    year_match = re.search(r'(\d{4})', name)
    year = year_match.group(1) if year_match else ''
    
    # 提取公司名（假设公司名在年份之前）
    if year:
        company_part = name.split(year)[0].strip()
    else:
        company_part = name
    
    # 替换非法字符为下划线
    company_part = re.sub(r'[^a-zA-Z0-9_]', '_', company_part)
    
    # 去除连续下划线
    company_part = re.sub(r'_+', '_', company_part)
    
    # 去除首尾下划线
    company_part = company_part.strip('_')
    
    # 转换为小写
    company_part = company_part.lower()
    
    # 确保不以数字开头
    if company_part and company_part[0].isdigit():
        company_part = 'company_' + company_part
    
    # 构建表名
    if company_part and year:
        table_name = f"{company_part}_{year}"
    elif company_part:
        table_name = company_part
    elif year:
        table_name = f"financial_report_{year}"
    else:
        table_name = "table"
    
    # 如果提供了文件内容哈希，添加到表名中确保唯一性
    if file_content_hash:
        # 取哈希值的前8位
        hash_suffix = file_content_hash[:8]
        table_name = f"{table_name}_{hash_suffix}"
    
    # 处理超长名称，如果长度超过64个字符，截断并添加哈希后缀
    if len(table_name) > 64:
        prefix = table_name[:20].rstrip('_')
        if not file_content_hash:
            file_content_hash = hashlib.md5(original_name.encode('utf-8')).hexdigest()
        hash_suffix = file_content_hash[:8]
        table_name = f"{prefix}_{hash_suffix}"
    
    return table_name