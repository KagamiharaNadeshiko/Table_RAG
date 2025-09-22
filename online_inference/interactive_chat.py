#!/usr/bin/env python3

import json
import argparse
import os
import sys
from typing import Dict, Any
from main import TableRAG
from chat_utils import init_logger
import logging

def create_sample_case(question: str, table_id: str = "auto") -> Dict[str, Any]:

    return {
        "question": question,
        "table_id": table_id  # 默認為"auto"，表示自動選擇表格
    }

def interactive_chat(args=None):
    """
    交互式聊天主函數（精簡版）
    """
    # 最小輸出模式：不打印橫幅/提示

    # 初始化TableRAG
    try:
        # 默認參數
        if args is None:
            parser = argparse.Namespace(
                backbone='qwen2.57b',
                doc_dir='../offline_data_ingestion_and_query_interface/data/schema',
                excel_dir='../offline_data_ingestion_and_query_interface/dataset/dev_excel',
                bge_dir='./bge_models',
                max_iter=5,
                table_id='auto',
                question='',
                tables=None,
                embedding_policy='build_if_missing'
            )
            args = parser

        agent = TableRAG(args)

        # 解析手動指定的多表（可多次 --tables 或逗號分隔）
        def _parse_tables(tables_opt):
            if not tables_opt:
                return []
            collected = []
            for item in tables_opt:
                if not item:
                    continue
                parts = [p.strip() for p in str(item).split(',') if str(p).strip()]
                collected.extend(parts)
            # 去重並保留順序
            seen = set()
            result = []
            for t in collected:
                key = t.lower()
                if key not in seen:
                    seen.add(key)
                    result.append(t)
            return result

        manual_tables = _parse_tables(getattr(args, 'tables', None))
        current_table_id = manual_tables if manual_tables else (getattr(args, 'table_id', 'auto') or 'auto')

    except Exception as e:
        print(f"初始化失敗: {e}")
        print("請檢查配置文件和數據路徑是否正確")
        return

    # 一次性模式：命令行同時提供 --question
    if getattr(args, 'question', None):
        try:
            case = create_sample_case(args.question, current_table_id if current_table_id else 'auto')
            if getattr(args, 'verbose', False):
                print("[TableRAG] 問題:", args.question)
                print("[TableRAG] 選表模式:", "手動多表" if isinstance(current_table_id, list) and current_table_id else ("手動單表" if (isinstance(current_table_id, str) and current_table_id not in (None, '', 'auto')) else "自動選表"))
                print("[TableRAG] 當前table_id:", current_table_id)
                print("[TableRAG] 開始推理...")
            answer, _ = agent._run(case, backbone=args.backbone)
            if getattr(args, 'verbose', False):
                print("[TableRAG] 結果:")
            print(answer or "")
        except Exception as e:
            print(f"處理問題時發生錯誤: {e}")
        return

    while True:
        try:
            # 獲取用戶輸入
            user_input = input("\n請輸入您的問題: ").strip()
            
            # 檢查退出命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("感謝使用 TableRAG，再見!")
                break
            
            # 檢查空輸入
            if not user_input:
                continue
            
            # 創建案例並運行TableRAG（支持auto/手動指定，手動可多表）
            case = create_sample_case(user_input, current_table_id)
            answer, messages = agent._run(case, backbone=args.backbone)
            
            # 僅輸出答案本身（若無則輸出空行）
            print(answer or "")
            
        except KeyboardInterrupt:
            print("\n\n用戶中斷，再見!")
            break
        except Exception as e:
            print(f"\n處理問題時發生錯誤: {e}")
            print("請嘗試重新表述您的問題或檢查系統配置")

def print_available_tables(agent):
    """
    顯示可用的表格列表
    """
    print("\n可用的表格列表:")
    print("-" * 40)
    
    try:
        # 獲取所有表格文件
        schema_dir = "../offline_data_ingestion_and_query_interface/data/schema"
        excel_dir = "../offline_data_ingestion_and_query_interface/dataset/dev_excel"
        
        tables = []
        
        # 從schema目錄獲取表格
        if os.path.exists(schema_dir):
            for file in os.listdir(schema_dir):
                if file.endswith('.json'):
                    table_name = file.replace('.json', '')
                    tables.append(table_name)
        
        # 從excel目錄獲取表格
        if os.path.exists(excel_dir):
            for file in os.listdir(excel_dir):
                if file.endswith(('.xlsx', '.xls', '.csv')):
                    table_name = file.replace('.xlsx', '').replace('.xls', '').replace('.csv', '')
                    if table_name not in tables:
                        tables.append(table_name)
        
        if tables:
            for i, table in enumerate(tables, 1):
                print(f"  {i}. {table}")
            print(f"\n共找到 {len(tables)} 個表格")
        else:
            print("未找到任何表格文件")
            print("請檢查數據目錄是否正確配置")
            
    except Exception as e:
        print(f"獲取表格列表失敗: {e}")

def print_help():
    """
    顯示幫助信息
    """
    print("\nTableRAG 使用幫助:")
    print("=" * 50)
    print("基本用法:")
    print("   • 直接輸入自然語言問題")
    print("   • 系統會自動選擇最相關的表格")
    print("   • 支持複雜的多步驟推理")
    print()
    print("問題示例:")
    print("   • '銷售額最高的產品是什麼？'")
    print("   • '計算每個部門的平均工資'")
    print("   • '找出年齡大於30歲的員工'")
    print("   • '按銷售額排序顯示前5名'")
    print()
    print("特殊命令:")
    print("   • 'help' - 顯示此幫助信息")
    print("   • 'tables' - 顯示可用表格列表")
    print("   • 'quit' - 退出程序")
    print()
    print("系統特點:")
    print("   • 智能表格選擇")
    print("   • 自然語言理解")
    print("   • 多跳推理能力")
    print("   • 詳細推理過程")
    print("=" * 50)

def main():
    """
    主函數
    """
    parser = argparse.ArgumentParser(description="TableRAG 交互式聊天（精簡）")
    parser.add_argument('--backbone', type=str, default='qwen2.57b', 
                       help='選擇LLM模型 (gpt-4o, qwen2.57b, qwen3_8b, v3)')
    parser.add_argument('--doc_dir', type=str, default='../offline_data_ingestion_and_query_interface/data/schema',
                       help='文檔目錄路徑')
    parser.add_argument('--excel_dir', type=str, default='../offline_data_ingestion_and_query_interface/dataset/dev_excel',
                       help='Excel文件目錄路徑')
    parser.add_argument('--bge_dir', type=str, default='./bge_models',
                       help='BGE模型目錄路徑')
    parser.add_argument('--table_id', type=str, default='auto',
                       help='指定表ID；不指定或auto為自動選表')
    parser.add_argument('--max_iter', type=int, default=5,
                       help='最大推理步數，需<=5')
    # 一次性模式的問題輸入
    parser.add_argument('--question', type=str, default='',
                       help='一次性模式：直接輸入問題，程序將輸出答案後退出')
    # 多表手動指定，可使用多次 --tables 或逗號分隔
    parser.add_argument('--tables', action='append', default=None,
                       help='一次性或交互模式：手動指定表名（可多次指定或逗號分隔），優先於 --table_id')
    # 調試輸出
    parser.add_argument('--verbose', action='store_true', default=False,
                        help='非交互一次性模式下，輸出關鍵過程信息便於調試')
    parser.add_argument('--embedding_policy', type=str, default='build_if_missing', choices=['load_only','build_if_missing','rebuild'])
    
    args = parser.parse_args()
    
    # 檢查必要目錄是否存在
    required_dirs = [args.doc_dir, args.excel_dir, args.bge_dir]
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            print(f" 目錄不存在: {dir_path}")
            print("請確保數據和模型文件已正確放置")
            return
    
    # 開始交互式聊天
    interactive_chat(args)

if __name__ == "__main__":
    main()
