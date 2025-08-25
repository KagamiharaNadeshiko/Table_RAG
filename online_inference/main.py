"""
Main Entry of TableRAG.
"""
import json
import argparse
import concurrent.futures
import os
from tqdm import tqdm
from chat_utils import *
from tools.retriever import *
from tools.sql_tool import *
from config import *
from utils.utils import read_in, read_in_lines, read_plain_csv
from utils.tool_utils import excel_to_markdown
from typing import Dict, Tuple, Any, List, Set
import threading
import traceback
import copy
import time
from prompt import *
from chat_utils import init_logger
import logging
from utils.canonical_table_map import CanonicalTableIndex

# 初始化logger
logger = init_logger('./logs/test.log', logging.INFO)


MAX_ITER = 5
ASSISTANT = "assistant"
FUNCTION = "function"


class TableRAG() :
    """
    Agent of TableRAG.
    """
    def __init__(self, _args: Any) -> None:
        self.config = _args
        self.max_iter = min(_args.max_iter, MAX_ITER)
        self.cnt = 0
        # Build canonical table mapping index
        self.table_index = CanonicalTableIndex(schema_dir=_args.doc_dir, excel_dir=_args.excel_dir)
        self.retriever = MixedDocRetriever(
            doc_dir_path=_args.doc_dir,
            excel_dir_path=_args.excel_dir,
            llm_path=os.path.join(_args.bge_dir, "bge-m3"),
            reranker_path=os.path.join(_args.bge_dir, "bge-reranker-v2-m3"),
            save_path="./embedding.pkl"
        )
        # self.repo_id = self.config.get("repo_id", "")
        self.repo_id = ""  # 初始化repo_id為空字符串
        self.function_lock = threading.Lock()

    def relate_to_table(self, doc_name: str) -> str :
        """
        Find the excel file according to json file.
        """
        if "json" in doc_name :
            table_file_name = doc_name.replace("json", "xlsx")
        if os.path.exists() :
            run_name = doc_name.replace(".json", "_sheet1.xlsx")
            return f"[\"{run_name}\"]"
        return ""

    def create_tools(self) :
        tools = [{
            "type": "function",
            "function": {
                "name": "solve_subquery",
                "description": "Return answer for the decomposed subquery.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subquery": {
                            "type": "string",
                            "description": "The subquery to be solved, only take natural language as input."
                        }
                    },
                    "required": [
                        "subquery"
                    ],
                    "additionalProperties": False
                },
                "strict": True
            }
        }]
        return tools

    def extract_subquery(self, response: Any, backbone: str = 'openai') -> Tuple[str, str] :
        """
        Extract the subquery and reasoning process.
        """
        subquery, tool_call_id = [], []
        if isinstance(response, dict) :
            if "tool_calls" in response and response["tool_calls"] :
                for call in response["tool_calls"] :
                    tool_call_id.append(call["id"])
                    arguments = call["function"]["arguments"]
                    subquery.append(json.loads(arguments)["subquery"])
                return response['content'], subquery, tool_call_id
            else :
                return response['content'], None, None
        
        reasoning = response.content
        try :
            for call in response.tool_calls :
                arguments = call.function.arguments
                subquery.append(json.loads(arguments)["subquery"])
                tool_call_id.append(call.id)
            return reasoning, subquery, tool_call_id
        except :
            return reasoning, None, None

    def extract_answer(self, response: str) -> str :
        ans = response[response.index("<Answer>") + len("<Answer>"): ] 
        return ans

    def extract_content(self, response: Any) -> str :
        try :
            return response.content
        except :
            return response['content']

    def get_llm_response(self, text_messages: object, tools: object, backbone: str, select_config: object) :
        if tools :
            response = get_chat_result(messages=text_messages, tools=tools, llm_config=select_config)   
        else :
            response = get_chat_result(messages=text_messages, tools=None, llm_config=select_config)   

        return response
                        

    def auto_select_table(self, query: str, top_k: int = 3) -> Tuple[str, List[str]]:
        """
        智能選擇最相關的表格，並用啟發式降低通用別名（如年份“2024”）干擾，
        優先選擇別名中包含查詢關鍵詞（如公司名）的表。
        
        Args:
            query: 用戶查詢
            top_k: 返回前k個最相關的表格（最終返回的相關表列表也不超過此數）
            
        Returns:
            Tuple[str, List[str]]: (最相關表格名, 相關表格列表)
        """
        # 使用檢索器獲取候選
        _, _, doc_filenames = self.retriever.retrieve(query, 30, max(top_k, 3))

        # 將檢索文件名映射為規範ID，並基於別名與查詢/文件名的匹配程度打分
        scored: List[Tuple[str, float]] = []  # (canonical_id, score)
        best_score_by_cid: Dict[str, float] = {}
        strong_match_by_cid: Dict[str, bool] = {}
        is_year_like_cid: Dict[str, bool] = {}

        # 提取查詢中的關鍵字串（簡單啟發式：長度>=2的連續中英文數字片段）
        try:
            import re as _re
            query_terms = [t for t in _re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", query) if len(t) >= 2]
        except Exception:
            query_terms = [query] if len(query) >= 2 else []

        def _alias_score(aliases: List[str]) -> float:
            score = 0.0
            for alias in aliases:
                lower_alias = alias.lower()
                # 降權：純年份/通用短別名
                if lower_alias.isdigit() and len(lower_alias) == 4:
                    score -= 2.0
                if len(lower_alias) <= 2:
                    score -= 0.5
                # 提升：別名包含查詢關鍵詞，或關鍵詞包含於別名
                for term in query_terms:
                    lower_term = term.lower()
                    if lower_term in lower_alias or lower_alias in lower_term:
                        score += 2.0
            return score

        for filename in doc_filenames:
            stem = filename.replace(".json", "").replace(".xlsx", "")
            cid = self.table_index.get_canonical_id(stem)
            if not cid:
                continue
            aliases = self.table_index.get_aliases(cid)
            score = _alias_score(aliases)
            # 文件名匹配加分
            lower_filename = stem.lower()
            for term in query_terms:
                lower_term = term.lower()
                if lower_term in lower_filename:
                    score += 3.0
            # 判斷強匹配（文件名或別名包含查詢詞）
            has_strong = False
            if any(t.lower() in lower_filename for t in query_terms):
                has_strong = True
            else:
                for alias in aliases:
                    la = alias.lower()
                    if any((t.lower() in la) or (la in t.lower()) for t in query_terms):
                        has_strong = True
                        break

            # 記錄是否為年份樣式的CID
            is_year_like = cid.isdigit() and len(cid) == 4

            # 同一規範ID取最高分
            if cid not in best_score_by_cid or score > best_score_by_cid[cid]:
                best_score_by_cid[cid] = score
                strong_match_by_cid[cid] = has_strong
                is_year_like_cid[cid] = is_year_like

        for cid, score in best_score_by_cid.items():
            scored.append((cid, score))

        # 優先：只保留強匹配的候選
        strong_scored = [(cid, sc) for cid, sc in scored if strong_match_by_cid.get(cid, False)]
        candidates = strong_scored if strong_scored else scored

        # 若仍無強匹配，避免選取年份類CID（如2024）除非其分數明顯高（>=1.0）
        if not strong_scored:
            filtered = []
            for cid, sc in candidates:
                if is_year_like_cid.get(cid, False) and sc < 1.0:
                    continue
                filtered.append((cid, sc))
            candidates = filtered if filtered else candidates

        # 如無候選，回退
        if not scored:
            return "sample_table", []

        # 依分數排序，分數相同保留原順序
        candidates.sort(key=lambda x: x[1], reverse=True)

        # 取前 top_k 作為相關表
        canonical_ids = [cid for cid, _ in candidates[:top_k]]
        top_table = canonical_ids[0]
        return top_table, canonical_ids

    def _run(self, case: dict, backbone: str, tmp: Any = None) :
        """
        Single iteration of TableRAG inference.
        """
        query = case["question"]
        
        # 智能表格選擇：如果沒有指定table_id或table_id為空，則自動選擇
        if "table_id" not in case or not case["table_id"] or case["table_id"] == "auto":
            top_table, related_tables = self.auto_select_table(query)
            logger.info(f"Auto-selected table: {top_table}")
            logger.info(f"Related tables: {related_tables}")
        else:
            # 使用用戶指定的表格
            table_id = case["table_id"]
            query_with_suffix = case['question'] + f"The given table is in {table_id}"
            _, _, doc_filenames = self.retriever.retrieve(query_with_suffix, 30, 5)
            top_table = doc_filenames[0].replace(".json", "").replace(".xlsx", "")
            related_tables = [top_table]

        # 将相关表格（规范ID）转换为适合SQL服务的别名集合
        related_table_name_list = []
        for cid in related_tables:
            for alias in self.table_index.best_service_aliases(cid):
                if alias not in related_table_name_list:
                    related_table_name_list.append(alias)

        tools = self.create_tools()
        current_iter = self.max_iter
        text_messages = self.construct_initial_prompt(case, top_table)

        logger.info(f"Processing query: {query}")
        logger.info(f"Using table: {top_table}")
        select_config = config_mapping[backbone]

        while current_iter :
            current_iter -= 1
            response = self.get_llm_response(text_messages=text_messages, tools=tools, backbone=backbone, select_config=select_config)

            reasoning, sub_queries, tool_call_ids = self.extract_subquery(response, backbone=backbone)
            logger.info(f"Step {self.max_iter - current_iter}: {sub_queries}")

            if not sub_queries and "<Answer>" in reasoning and current_iter != self.max_iter - 1 :
                answer = self.extract_answer(reasoning)
                logger.info(f"Answer: {answer}")
                return answer, text_messages
            
            if not sub_queries :
                # Prompt the model to synthesize a final answer when no new tool call is made
                text_messages.append({
                    "role": "user",
                    "content": (
                        "If you have sufficient information from prior subquery answers, "
                        "please provide the final answer now using the exact format:\n"
                        "<Answer>: [your complete response]"
                    )
                })
                continue

            messages = response
            text_messages.append(messages)

            for sub_query, tool_call_id in zip(sub_queries, tool_call_ids) :
                reranked_docs, _, _ = self.retriever.retrieve(sub_query, 30, 5)
                unique_retriebed_docs = list(set(reranked_docs))
                doc_content = "\n".join([r for r in unique_retriebed_docs[:3]])

                excel_rag_response_dict = get_excel_rag_response_plain(related_table_name_list, sub_query)
                excel_rag_response = copy.deepcopy(excel_rag_response_dict)
                logger.info(f"Requesting ExcelRAG, source file {str(related_table_name_list)}, with query {sub_query}")

                try :
                    sql_str = excel_rag_response['sql_str']
                    sql_execute_result = excel_rag_response['sql_execution_result']
                    schema  = excel_rag_response['nl2sql_prompt'].split('Based on the schemas above, please use MySQL syntax to solve the following problem')[0].strip()
                except :
                    sql_str, sql_execute_result, schema = "ExcelRAG execute fails, key does not exists."

                combine_prompt_formatted = COMBINE_PROMPT.format(
                    docs=doc_content, 
                    schema=schema, 
                    nl2sql_model_response=sql_str, 
                    sql_execute_result=sql_execute_result,
                    query=sub_query
                )

                final_prompt = combine_prompt_formatted

                msg = [{"role": "user", "content": final_prompt}]
                answer = self.get_llm_response(text_messages=msg, backbone=backbone, select_config=select_config, tools=None)
                answer = self.extract_content(answer)

                if not answer :
                    answer = ""
                
                logger.info(f"LLM Subquery Answer: {answer}")
                execution_message = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": "Subquery Answer: " + answer
                }
                text_messages.append(execution_message)

                # Nudge the assistant to proceed and produce the final answer if ready
                text_messages.append({
                    "role": "user",
                    "content": (
                        "Continue reasoning based on the subquery answer above. "
                        "If the information is sufficient, output the final answer now in the format:\n"
                        "<Answer>: [your complete response]"
                    )
                })

        return None, text_messages


    def construct_initial_prompt(self, case: dict, top1_table_name: str) -> Any :
        query = case["question"]
        # top1_table_name 现在是规范ID，优先寻找对应excel文件
        markdown_text = "Can NOT find table content!"
        preferred_excel = None
        cid = self.table_index.get_canonical_id(top1_table_name) or top1_table_name
        preferred_excel = self.table_index.get_preferred_excel_file(cid)
        if preferred_excel:
            stem, ext = os.path.splitext(preferred_excel)
            # 如果存在同名csv，则优先读取csv为markdown
            csv_path = os.path.join(self.config.excel_dir, stem + ".csv")
            if os.path.exists(csv_path):
                markdown_text = read_plain_csv(csv_path)
            else:
                # 回退读取xlsx为markdown
                excel_path = os.path.join(self.config.excel_dir, preferred_excel)
                if os.path.exists(excel_path):
                    markdown_text = excel_to_markdown(excel_path)
        
        inital_prompt = SYSTEM_EXPLORE_PROMPT.format(query=query, table_content=markdown_text)
        logger.info(f"Inital prompt: {inital_prompt}")

        intial_msg = [{"role": "user", "content": inital_prompt}]
        return intial_msg
    
    def run(
        self,
        file_path: str,
        save_file_path: str,
        backbone: str,
        rerun: bool = False,
        max_workers: int = 1
    ) -> None :
        """
        Experimental Entry.
        """
        if rerun :
            pre_data = read_in_lines(save_file_path)
            pre_questions = {case["question"] for case in pre_data}

        else :
            pre_questions = {}
        src_data = read_in(file_path)

        def process_data(case) :
            if case["question"] in pre_questions :
                return pre_questions[case["question"]]
            
            # 支持智能表格選擇：如果沒有table_id或為"auto"，則自動選擇
            if "table_id" not in case or not case["table_id"] or case["table_id"] == "auto":
                logger.info(f"Auto-selecting table for question: {case['question']}")
                case["table_id"] = "auto"  # 確保設置為auto
            
            answer, messages = self._run(case, backbone=backbone)
            
            result = case.copy()
            if answer == None :
                result["tablerag_answer"] = ""
                result["tablerag_messages"] = []
            else :
                new_messages = []
                for mes in messages :
                    if not isinstance(mes, dict) :
                        new_messages.append(mes.to_dict())
                    else :
                        new_messages.append(mes)
                result["tablerag_answer"] = answer
                result["tablerage_messages"] = new_messages

            return result

        if max_workers >= 1 :
            file_lock = threading.Lock()
            with open(save_file_path, "w", encoding="utf-8") as fout :
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor :
                    futures = []
                    for case in src_data :
                        future = executor.submit(process_data, case)
                        futures.append((future, case["question"]))
                    
                    for future, question_id in tqdm(futures, desc="handling questions") :
                        try :
                            result = future.result()
                            with file_lock :
                                json.dump(result, fout)
                                fout.write("\n")
                                fout.flush()
                        except Exception as e :
                            print(f"Failed to get result for {question_id}: {e}")
                            traceback.print_exc()

if __name__ == "__main__" :
    parser = argparse.ArgumentParser(description="entry args")
    parser.add_argument('--backbone', type=str, default="gpt-4o")
    parser.add_argument('--data_file_path', type=str, default="", help="source file path")
    parser.add_argument('--doc_dir', type=str, default="", help="source file path")
    parser.add_argument('--excel_dir', type=str, default="", help="source file path")
    parser.add_argument('--bge_dir', type=str, default="", help="source file path")
    parser.add_argument('--save_file_path', type=str, default="")
    parser.add_argument('--max_iter', type=int, default=5)
    parser.add_argument('--rerun', type=bool, default=False)
    _args, _unparsed = parser.parse_known_args()

    agent = TableRAG(_args)
    start_time = time.time()
    agent.run(
        file_path=_args.data_file_path,
        save_file_path=_args.save_file_path,
        backbone=_args.backbone,
        rerun=_args.rerun
    )
    end_time = time.time()
    print(f"Processing data consumes: {end_time - start_time:.6f} s.")

