#!/usr/bin/env python3
"""
Interactive Chat Interface for TableRAG
使用自然語言與TableRAG進行交互式對話
"""

import json
import argparse
import os
import sys
from typing import Dict, Any
from main import TableRAG
from chat_utils import init_logger
import logging

def create_sample_case(question: str, table_id: str = "auto") -> Dict[str, Any]:
    """
    創建一個樣本案例用於TableRAG處理
    支持智能表格選擇：當table_id為"auto"時，系統會自動選擇最相關的表格
    """
    return {
        "question": question,
        "table_id": table_id  # 默認為"auto"，表示自動選擇表格
    }

def interactive_chat():
    """
    交互式聊天主函數
    """
    print("🚀 歡迎使用 TableRAG 智能表格查詢系統!")
    print("=" * 60)
    print("💡 您可以直接問我關於數據的問題，系統會自動選擇最相關的表格：")
    print("   📊 '這個表格中有多少行數據？'")
    print("   📈 '找出銷售額最高的產品'")
    print("   💰 '計算平均價格'")
    print("   🏆 '顯示前10名的記錄'")
    print("   📋 '列出所有部門的員工數量'")
    print("=" * 60)
    print("🎯 系統特點：")
    print("   ✅ 智能表格選擇 - 無需指定表格名稱")
    print("   ✅ 自然語言查詢 - 直接問問題即可")
    print("   ✅ 多跳推理 - 支持複雜問題分析")
    print("   ✅ 詳細推理過程 - 可查看分析步驟")
    print("=" * 60)
    print("💬 輸入 'quit' 或 'exit' 退出聊天")
    print("❓ 輸入 'help' 查看幫助信息")
    print("🔍 輸入 'tables' 查看可用的表格列表")
    print("=" * 60)

    # 初始化TableRAG
    try:
        # 創建參數對象
        class Args:
            def __init__(self):
                self.backbone = "gpt-4o"  # 可以修改為其他模型
                self.doc_dir = "./data/schema"  # 文檔目錄
                self.excel_dir = "./data/dataset/dev_excel"  # Excel文件目錄
                self.bge_dir = "./bge_models"  # BGE模型目錄
                self.max_iter = 5

        args = Args()
        
        print("🔄 正在初始化 TableRAG...")
        agent = TableRAG(args)
        print("✅ TableRAG 初始化完成!")
        print()

    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        print("請檢查配置文件和數據路徑是否正確")
        return

    while True:
        try:
            # 獲取用戶輸入
            user_input = input("\n🤔 請輸入您的問題: ").strip()
            
            # 檢查退出命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 感謝使用 TableRAG，再見!")
                break
            
            # 檢查幫助命令
            if user_input.lower() in ['help', 'h']:
                print_help()
                continue
            
            # 檢查表格列表命令
            if user_input.lower() in ['tables', 'table', 't']:
                print_available_tables(agent)
                continue
            
            # 檢查空輸入
            if not user_input:
                print("⚠️ 請輸入有效的問題")
                continue
            
            print(f"\n🔍 正在處理您的問題: {user_input}")
            print("⏳ 請稍候...")
            
            # 創建案例並運行TableRAG（使用智能表格選擇）
            case = create_sample_case(user_input, "auto")
            answer, messages = agent._run(case, backbone=args.backbone)
            
            # 顯示結果
            print("\n" + "="*60)
            print("📊 查詢結果:")
            print("="*60)
            
            if answer:
                print(f"✅ 答案: {answer}")
            else:
                print("❌ 無法找到答案")
                print("💡 請嘗試重新表述您的問題")
            
            # 顯示推理過程（可選）
            show_details = input("\n🔍 是否顯示詳細推理過程? (y/n): ").strip().lower()
            if show_details in ['y', 'yes']:
                print("\n📝 推理過程:")
                print("-" * 40)
                for i, msg in enumerate(messages):
                    if isinstance(msg, dict):
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        if content:
                            print(f"🔹 步驟 {i+1} ({role}): {content[:200]}...")
                    else:
                        print(f"🔹 步驟 {i+1}: {str(msg)[:200]}...")
            
            print("\n" + "="*60)
            
        except KeyboardInterrupt:
            print("\n\n👋 用戶中斷，再見!")
            break
        except Exception as e:
            print(f"\n❌ 處理問題時發生錯誤: {e}")
            print("💡 請嘗試重新表述您的問題或檢查系統配置")

def print_available_tables(agent):
    """
    顯示可用的表格列表
    """
    print("\n📋 可用的表格列表:")
    print("-" * 40)
    
    try:
        # 獲取所有表格文件
        schema_dir = "./data/schema"
        excel_dir = "./data/dataset/dev_excel"
        
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
                if file.endswith(('.xlsx', '.csv')):
                    table_name = file.replace('.xlsx', '').replace('.csv', '')
                    if table_name not in tables:
                        tables.append(table_name)
        
        if tables:
            for i, table in enumerate(tables, 1):
                print(f"  {i}. {table}")
            print(f"\n📊 共找到 {len(tables)} 個表格")
        else:
            print("❌ 未找到任何表格文件")
            print("💡 請檢查數據目錄是否正確配置")
            
    except Exception as e:
        print(f"❌ 獲取表格列表失敗: {e}")

def print_help():
    """
    顯示幫助信息
    """
    print("\n📖 TableRAG 使用幫助:")
    print("=" * 50)
    print("🎯 基本用法:")
    print("   • 直接輸入自然語言問題")
    print("   • 系統會自動選擇最相關的表格")
    print("   • 支持複雜的多步驟推理")
    print()
    print("💡 問題示例:")
    print("   • '銷售額最高的產品是什麼？'")
    print("   • '計算每個部門的平均工資'")
    print("   • '找出年齡大於30歲的員工'")
    print("   • '按銷售額排序顯示前5名'")
    print()
    print("🔧 特殊命令:")
    print("   • 'help' - 顯示此幫助信息")
    print("   • 'tables' - 顯示可用表格列表")
    print("   • 'quit' - 退出程序")
    print()
    print("⚡ 系統特點:")
    print("   • 智能表格選擇")
    print("   • 自然語言理解")
    print("   • 多跳推理能力")
    print("   • 詳細推理過程")
    print("=" * 50)

def main():
    """
    主函數
    """
    parser = argparse.ArgumentParser(description="TableRAG 交互式聊天界面")
    parser.add_argument('--backbone', type=str, default='gpt-4o', 
                       help='選擇LLM模型 (gpt-4o, qwen2.57b, v3)')
    parser.add_argument('--doc_dir', type=str, default='./data/schema',
                       help='文檔目錄路徑')
    parser.add_argument('--excel_dir', type=str, default='./data/dataset/dev_excel',
                       help='Excel文件目錄路徑')
    parser.add_argument('--bge_dir', type=str, default='./bge_models',
                       help='BGE模型目錄路徑')
    
    args = parser.parse_args()
    
    # 檢查必要目錄是否存在
    required_dirs = [args.doc_dir, args.excel_dir, args.bge_dir]
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            print(f" 目錄不存在: {dir_path}")
            print("請確保數據和模型文件已正確放置")
            return
    
    # 初始化日誌
    init_logger('interactive_chat', logging.INFO, 'interactive_chat.log')
    
    # 開始交互式聊天
    interactive_chat()

if __name__ == "__main__":
    main()
