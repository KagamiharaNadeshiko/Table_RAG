import os
import argparse
from online_inference.tools.retriever import MixedDocRetriever


def main():
    parser = argparse.ArgumentParser(description="Build or rebuild document embeddings for TableRAG retriever")

    # Resolve repository root (parent of this file's directory: online_inference/..)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, os.pardir))

    default_doc_dir = os.path.join(repo_root, 'offline_data_ingestion_and_query_interface', 'data', 'schema')
    default_excel_dir = os.path.join(repo_root, 'offline_data_ingestion_and_query_interface', 'dataset', 'dev_excel')
    default_bge_dir = os.path.join(repo_root, 'online_inference', 'bge_models')

    parser.add_argument('--doc_dir', type=str, default=default_doc_dir, help='Schema/doc directory path')
    parser.add_argument('--excel_dir', type=str, default=default_excel_dir, help='Excel directory path')
    parser.add_argument('--bge_dir', type=str, default=default_bge_dir, help='BGE models root directory')
    # default to embedding.pkl under the online_inference directory regardless of CWD
    default_save_path = os.path.join(script_dir, 'embedding.pkl')
    parser.add_argument('--save_path', type=str, default=default_save_path, help='Where to store embeddings pkl')
    parser.add_argument('--policy', type=str, default='rebuild', choices=['rebuild','build_if_missing','load_only'], help='Embedding policy')

    args = parser.parse_args()

    retriever = MixedDocRetriever(
        doc_dir_path=args.doc_dir,
        excel_dir_path=args.excel_dir,
        llm_path=os.path.join(args.bge_dir, "bge-m3"),
        reranker_path=os.path.join(args.bge_dir, "bge-reranker-v2-m3"),
        save_path=args.save_path,
        embedding_policy=args.policy
    )

    # Side-effects of constructor perform the embedding build/load.
    print(f"Embedding index ready at {args.save_path} with policy={args.policy}")


if __name__ == '__main__':
    main()


