#!/usr/bin/env python3
"""
清空数据库脚本
用于清空TableRAG数据库中的所有表，为重新导入数据做准备
"""

import sys
import os
import json
from offline_data_ingestion_and_query_interface.src.common_utils import sql_alchemy_helper

def clear_all_tables():
    """
    清空数据库中的所有表
    """
    print("正在获取数据库中的所有表...")
    
    try:
        # 获取所有表名
        result = sql_alchemy_helper.fetchall('SHOW TABLES')
        print(f"找到 {len(result)} 个表")
        
        if not result:
            print("数据库中没有表，无需清空")
            return
        
        # 解析JSON字符串结果
        if isinstance(result, str):
            result_data = json.loads(result)
        else:
            result_data = result
        
        # 提取表名
        table_names = []
        for row in result_data:
            # 表名在 'Tables_in_tablerag' 键中
            table_name = list(row.values())[0]
            table_names.append(table_name)
        
        print("准备清空的表:")
        for i, table_name in enumerate(table_names, 1):
            print(f"  {i}. {table_name}")
        
        # 确认操作
        confirm = input(f"\n确认要清空这 {len(table_names)} 个表吗？(y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("操作已取消")
            return
        
        print("\n开始清空表...")
        
        # 逐个删除表
        for i, table_name in enumerate(table_names, 1):
            try:
                print(f"正在删除表 {i}/{len(table_names)}: {table_name}")
                sql_alchemy_helper.execute_sql(f'DROP TABLE IF EXISTS `{table_name}`')
                print(f"  ✓ 表 {table_name} 已删除")
            except Exception as e:
                print(f"  ✗ 删除表 {table_name} 失败: {e}")
        
        print(f"\n清空完成！共处理了 {len(table_names)} 个表")
        
        # 验证清空结果
        remaining_tables = sql_alchemy_helper.fetchall('SHOW TABLES')
        if not remaining_tables:
            print("✓ 数据库已完全清空")
        else:
            print(f"⚠ 仍有 {len(remaining_tables)} 个表未删除")
            
    except Exception as e:
        print(f"清空数据库时发生错误: {e}")
        return False
    
    return True

def main():

    
    try:
        # 测试数据库连接
        print("正在测试数据库连接...")
        sql_alchemy_helper.fetchall('SELECT 1')
        print("✓ 数据库连接正常")
        
        # 清空所有表
        success = clear_all_tables()
        
        if success:
            print("\n" + "=" * 60)
            print("数据库清空完成！")
            print("现在可以重新运行数据导入脚本了。")
            print("=" * 60)
        else:
            print("\n数据库清空失败，请检查错误信息。")
            
    except Exception as e:
        print(f"操作失败: {e}")
        print("请检查数据库配置和连接。")

if __name__ == "__main__":
    main()
