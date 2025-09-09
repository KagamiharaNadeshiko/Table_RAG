import os
import sys
import json
import argparse
from typing import List, Tuple, Dict, Set

from offline_data_ingestion_and_query_interface.src.common_utils import SCHEMA_DIR, transfer_name, sql_alchemy_helper, PROJECT_ROOT
from offline_data_ingestion_and_query_interface.src.log_service import logger


def normalize_excel_filename(name: str) -> str:
    """
    Normalize input to an Excel filename.
    If no extension is provided, default to .xlsx
    """
    if name.lower().endswith('.xlsx') or name.lower().endswith('.xls'):
        return name
    return f"{name}.xlsx"


def get_base_table_name_from_excel(excel_filename: str) -> str:
    """
    Derive the base table name from the original Excel filename
    using transfer_name without file hash.
    """
    # only the filename part is relevant for transfer_name semantics
    original_name = os.path.basename(excel_filename)
    return transfer_name(original_name)


def list_matching_schema_files(base_table_name: str) -> List[str]:
    """
    List schema JSON files that match the base table name.
    A match is either exactly base_table_name.json or startswith base_table_name + '_'.
    Returns absolute file paths.
    """
    if not os.path.isdir(SCHEMA_DIR):
        return []

    result = []
    for filename in os.listdir(SCHEMA_DIR):
        if not filename.endswith('.json'):
            continue
        if filename == f"{base_table_name}.json" or filename.startswith(f"{base_table_name}_"):
            result.append(os.path.join(SCHEMA_DIR, filename))
    return result


def list_matching_excel_files(original_targets: List[str]) -> List[str]:
    """
    Find Excel files in dataset/dev_excel matching the provided original filenames.
    Returns absolute file paths.
    """
    excel_dir = os.path.join(PROJECT_ROOT, 'dataset', 'dev_excel')
    if not os.path.isdir(excel_dir):
        return []

    # Normalize (ensure extension)
    normalized = [normalize_excel_filename(t) for t in original_targets]

    candidates = set(normalized)
    results: List[str] = []
    for fname in os.listdir(excel_dir):
        if not (fname.lower().endswith('.xlsx') or fname.lower().endswith('.xls')):
            continue
        if fname in candidates:
            results.append(os.path.join(excel_dir, fname))

    return results


def resolve_table_names_from_schema_files(schema_files: List[str]) -> Tuple[Set[str], Dict[str, str], List[str]]:
    """
    Read each schema JSON and extract table_name.
    Returns (table_names_set, file_to_table_name_map, failed_files)
    """
    table_names: Set[str] = set()
    mapping: Dict[str, str] = {}
    failed: List[str] = []

    for path in schema_files:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            table_name = data.get('table_name')
            if not table_name:
                raise ValueError('Missing table_name in schema JSON')
            mapping[path] = table_name
            table_names.add(table_name)
        except Exception as e:
            logger.error(f"Failed to read schema file {path}: {e}")
            failed.append(path)

    return table_names, mapping, failed


def drop_tables(table_names: Set[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Drop each table if exists. Returns (dropped, errors)
    errors contains tuples of (table_name, error_message)
    """
    dropped: List[str] = []
    errors: List[Tuple[str, str]] = []
    for name in sorted(table_names):
        try:
            sql_alchemy_helper.execute_sql(f"DROP TABLE IF EXISTS `{name}`")
            logger.info(f"Dropped table: {name}")
            dropped.append(name)
        except Exception as e:
            logger.error(f"Failed to drop table {name}: {e}")
            errors.append((name, str(e)))
    return dropped, errors


def remove_files(file_paths: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """
    Delete files. Returns (removed, errors)
    errors contains tuples of (path, error_message)
    """
    removed: List[str] = []
    errors: List[Tuple[str, str]] = []
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Removed schema file: {path}")
                removed.append(path)
            else:
                logger.info(f"Schema file already absent: {path}")
        except Exception as e:
            logger.error(f"Failed to remove file {path}: {e}")
            errors.append((path, str(e)))
    return removed, errors


def present_plan(targets: List[str], base_names: List[str], schema_files: List[str], file_to_table: Dict[str, str], excel_files: List[str]) -> None:
    print("=== Deletion Plan ===")
    print("Targets (original Excel filenames):")
    for t in targets:
        print(f"  - {t}")
    print("\nResolved base table names:")
    for b in base_names:
        print(f"  - {b}")
    print("\nExcel files to delete:")
    if excel_files:
        for p in excel_files:
            print(f"  - {p}")
    else:
        print("  (none)")
    print("\nSchema files to delete:")
    if schema_files:
        for p in schema_files:
            tname = file_to_table.get(p, '(unknown)')
            print(f"  - {p}  -> table `{tname}`")
    else:
        print("  (none)")
    print()


def confirm_proceed(assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        answer = input("Proceed with deletion? (y/N): ").strip().lower()
        return answer in ('y', 'yes')
    except EOFError:
        # Non-interactive environment: default to no
        return False


def run_cleanup(targets: List[str], assume_yes: bool, dry_run: bool) -> int:
    if not targets:
        print("No targets provided. Use --target <excel_filename>.")
        return 2

    normalized = [normalize_excel_filename(t) for t in targets]
    base_names = [get_base_table_name_from_excel(t) for t in normalized]

    # gather all matching schema files
    all_schema_files: List[str] = []
    for base in base_names:
        matches = list_matching_schema_files(base)
        all_schema_files.extend(matches)

    # find matching excel files
    excel_files = list_matching_excel_files(normalized)

    # de-duplicate while preserving order
    seen = set()
    dedup_schema_files: List[str] = []
    for p in all_schema_files:
        if p not in seen:
            dedup_schema_files.append(p)
            seen.add(p)

    table_names, file_to_table, failed_files = resolve_table_names_from_schema_files(dedup_schema_files)

    present_plan(normalized, base_names, dedup_schema_files, file_to_table, excel_files)

    if dry_run:
        print("Dry-run enabled. No changes were made.")
        return 0

    if not confirm_proceed(assume_yes):
        print("Aborted by user.")
        return 1

    dropped, drop_errors = drop_tables(table_names)
    removed, remove_errors = remove_files(dedup_schema_files)
    removed_excels, remove_excel_errors = remove_files(excel_files)

    print("=== Summary ===")
    print(f"Tables dropped: {len(dropped)}")
    print(f"Schema files removed: {len(removed)}")
    print(f"Excel files removed: {len(removed_excels)}")
    if failed_files:
        print(f"Schema files failed to read: {len(failed_files)}")
    if drop_errors:
        print(f"Table drop errors: {len(drop_errors)}")
    if remove_errors:
        print(f"File remove errors: {len(remove_errors)}")
    if remove_excel_errors:
        print(f"Excel remove errors: {len(remove_excel_errors)}")

    # Non-zero exit if any errors occurred
    had_errors = bool(failed_files or drop_errors or remove_errors or remove_excel_errors)
    return 0 if not had_errors else 3


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete TableRAG schema files and corresponding MySQL tables by original Excel filename(s)."
    )
    parser.add_argument(
        '--target', action='append', default=[], metavar='EXCEL_FILENAME',
        help='Original Excel filename to delete (can be repeated). If no extension, .xlsx is assumed.'
    )
    parser.add_argument(
        '--yes', action='store_true', help='Skip confirmation prompt.'
    )
    parser.add_argument(
        '--dry-run', action='store_true', help='Preview actions without making changes.'
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return run_cleanup(targets=args.target, assume_yes=args.yes, dry_run=args.dry_run)


if __name__ == '__main__':
    sys.exit(main())


