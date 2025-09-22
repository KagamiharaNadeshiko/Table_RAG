import os
import pandas as pd
import json
import random as randum
from tqdm import tqdm
try:
    from .dtype_mapping import (
        INTEGER_DTYPE_MAPPING,
        FLOAT_DTYPE_MAPPING,
        OTHER_DTYPE_MAPPING,
        SPECIAL_INTEGER_DTYPE_MAPPING
    )
except ImportError:
    from dtype_mapping import (
        INTEGER_DTYPE_MAPPING,
        FLOAT_DTYPE_MAPPING,
        OTHER_DTYPE_MAPPING,
        SPECIAL_INTEGER_DTYPE_MAPPING
    )
import warnings
try:
    from offline_data_ingestion_and_query_interface.src.common_utils import transfer_name, SCHEMA_DIR, sql_alchemy_helper, PROJECT_ROOT
except ImportError:
    from offline_data_ingestion_and_query_interface.src.common_utils import transfer_name, SCHEMA_DIR, sql_alchemy_helper, PROJECT_ROOT
import hashlib
from .log_service import logger
import io

# Optional: detect xlrd availability and version for better diagnostics
try:
    import xlrd as _xlrd  # type: ignore
    _XLRD_VERSION = getattr(_xlrd, "__version__", "unknown")
except Exception:
    _xlrd = None
    _XLRD_VERSION = None

# Optional: msoffcrypto for encrypted Excel
try:
    import msoffcrypto
except Exception:
    msoffcrypto = None  # type: ignore


def _is_zip_xlsx(path: str) -> bool:
    """粗略判断文件是否为 ZIP 结构（xlsx 常见），用于误后缀 .xls 但实际是 .xlsx 的情况。"""
    try:
        with open(path, "rb") as f:
            sig = f.read(4)
            return sig == b"PK\x03\x04"
    except Exception:
        return False


def _try_decrypt_excel_if_needed(path: str) -> io.BytesIO | None:
    """尝试用 msoffcrypto 解密受保护的 Excel，成功返回解密后的 BytesIO，失败返回 None。
    密码从环境变量 EXCEL_PASSWORD 读取。
    """
    if msoffcrypto is None:
        return None
    password = os.getenv("EXCEL_PASSWORD")
    if not password:
        return None
    try:
        with open(path, "rb") as f:
            office_file = msoffcrypto.OfficeFile(f)
            office_file.load_key(password=password)
            out = io.BytesIO()
            office_file.decrypt(out)
            out.seek(0)
            return out
    except Exception as e:
        logger.warning(f"msoffcrypto 解密失败: path={path}, error={e}")
        return None


def infer_and_convert(series):
    # 尝试转换为整数
    try:
        return pd.to_numeric(series, downcast='integer')
    except ValueError:
        pass

    # 尝试转换为浮点数
    try:
        return pd.to_numeric(series, downcast='float')
    except ValueError:
        pass

    # 尝试转换为日期时间
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # 忽略特定类型的警告
            return pd.to_datetime(series)
    except ValueError:
        pass

    # 如果都不行，返回原始数据
    return series


def pandas_to_mysql_dtype(dtype):
    if pd.api.types.is_integer_dtype(dtype):
        if str(dtype) in SPECIAL_INTEGER_DTYPE_MAPPING:
            return SPECIAL_INTEGER_DTYPE_MAPPING[str(dtype)]
        return INTEGER_DTYPE_MAPPING.get(dtype, 'INT')

    elif pd.api.types.is_float_dtype(dtype):
        return FLOAT_DTYPE_MAPPING.get(dtype, 'FLOAT')

    elif pd.api.types.is_bool_dtype(dtype):
        return OTHER_DTYPE_MAPPING['boolean']

    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return OTHER_DTYPE_MAPPING['datetime']

    elif pd.api.types.is_timedelta64_dtype(dtype):
        return OTHER_DTYPE_MAPPING['timedelta']

    elif pd.api.types.is_string_dtype(dtype):
        return OTHER_DTYPE_MAPPING['string']

    elif pd.api.types.is_categorical_dtype(dtype):
        return OTHER_DTYPE_MAPPING['category']

    else:
        return OTHER_DTYPE_MAPPING['default']

def get_sample_values(series):
    valid_values = [str(x) for x in series.dropna().unique() if pd.notnull(x) and len(str(x)) < 64]
    sample_values = randum.sample(valid_values, min(3, len(valid_values)))
    return sample_values if sample_values else ['no sample values available']

def get_schema_and_data(df):
    column_list = []
    for col in df.columns:
        cur_column_list = []
        if isinstance(df[col], pd.DataFrame):
            print(f"Column {col} is a DataFrame, skipping...")
            raise ValueError(f"Column {col} is a DataFrame, which is not supported.")   
        cur_column_list.append(col)
        cur_column_list.append(pandas_to_mysql_dtype(df[col].dtype))
        cur_column_list.append('sample values:' + str(get_sample_values(df[col])))

        # 形成三元组
        column_list.append(cur_column_list)

    return column_list

def generate_schema_info(df: pd.DataFrame, file_name: str, file_content_hash: str = None):
    try:
        column_list = get_schema_and_data(df)
    except:
        print(f"{file_name} 列存在问题")
        raise ValueError(f"Error processing file: {file_name}")

    table_name = transfer_name(file_name, file_content_hash)

    schema_dict = {
        'table_name': table_name,
        'column_list': column_list,
        'original_filename': file_name,
        'source_file_hash': file_content_hash
    }

    return schema_dict, table_name


def transfer_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗 DataFrame 的列名：
    1. 使用 transfer_name_func 转换列名。
    2. 如果第一个列名为空或 NaN，设置为 'No'。
    3. 处理重复列名，重复列名加后缀 _1, _2 等。

    参数：
        df: 需要处理列名的 DataFrame。
        transfer_name_func: 一个函数，用于转换列名（如去除空格、统一格式等）。

    返回：
        列名处理后的 DataFrame。
    """
    df = df.copy()

    # 第一步：统一转换列名
    df.columns = [transfer_name(col) for col in df.columns]

    # 第二步：首列为空或 NaN 时命名为 'No'
    df.columns = [
        'No' if i == 0 and (not col or pd.isna(col)) else col
        for i, col in enumerate(df.columns)
    ]

    # 第三步：处理重复列名
    seen = {}
    new_columns = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_columns.append(col)
    df.columns = new_columns

    return df


def _read_excel_with_fallbacks(full_path: str, file_name: str) -> pd.DataFrame:
    """尽可能健壮地读取 Excel：
    - .xlsx: 优先 openpyxl
    - .xls: 依次尝试 pandas 默认(None) → xlrd → 手工 xlrd 解析 → 最后报出清晰提示
    """
    ext = os.path.splitext(file_name)[1].lower()
    errors = []

    if ext == '.xlsx':
        try:
            return pd.read_excel(full_path, engine='openpyxl')
        except Exception as e:
            logger.exception(f"读取 .xlsx 失败: path={full_path}, engine=openpyxl, error={e}")
            raise

    # .xls 强制仅走 xlrd
    try:
        # 若可能加密，尝试解密后用 xlrd 读取 BytesIO
        decrypted = _try_decrypt_excel_if_needed(full_path)
        if decrypted is not None:
            if _xlrd is None:
                raise RuntimeError("xlrd 未安装")
            if _XLRD_VERSION and str(_XLRD_VERSION).split('.')[0].isdigit() and int(str(_XLRD_VERSION).split('.')[0]) >= 2:
                raise RuntimeError(f"xlrd 版本为 {_XLRD_VERSION}，不再支持 .xls（请安装 xlrd==1.2.0）")
            logger.info(f"使用 xlrd 读取已解密的 .xls BytesIO")
            return pd.read_excel(decrypted, engine='xlrd')

        if _xlrd is None:
            raise RuntimeError("xlrd 未安装")
        if _XLRD_VERSION and str(_XLRD_VERSION).split('.')[0].isdigit() and int(str(_XLRD_VERSION).split('.')[0]) >= 2:
            raise RuntimeError(f"xlrd 版本为 {_XLRD_VERSION}，不再支持 .xls（请安装 xlrd==1.2.0）")
        logger.info(f"严格模式：使用 xlrd 读取 .xls: path={full_path}, xlrd_version={_XLRD_VERSION}")
        return pd.read_excel(full_path, engine='xlrd')
    except Exception as e:
        errors.append(f"xlrd 失败: {e}")
        logger.warning(f"严格模式 xlrd 读取 .xls 失败: path={full_path}, error={e}")

    # 汇总错误并给出指引
    hint = (
        "无法读取 .xls。请安装兼容版本的 xlrd：pip install xlrd==1.2.0\n"
        f"错误详情：{' | '.join(errors)}"
    )
    logger.error(hint)
    raise RuntimeError(hint)


def parse_excel_file_and_insert_to_db(excel_file_outer_dir: str):
    if not os.path.exists(excel_file_outer_dir):
        raise FileNotFoundError(f"File not found: {excel_file_outer_dir}")
    
    # 确保 schema 目录存在
    if not os.path.exists(SCHEMA_DIR):
        os.makedirs(SCHEMA_DIR)
        logger.info(f"已创建 schema 目录: {SCHEMA_DIR}")
    else:
        logger.info(f"使用现有 schema 目录: {SCHEMA_DIR}")

    # 记录导入的根目录信息
    try:
        abs_excel_dir = os.path.abspath(excel_file_outer_dir)
    except Exception:
        abs_excel_dir = excel_file_outer_dir
    try:
        abs_schema_dir = os.path.abspath(SCHEMA_DIR)
    except Exception:
        abs_schema_dir = SCHEMA_DIR
    logger.info(f"开始导入 Excel 目录: excel_dir={abs_excel_dir}, schema_dir={abs_schema_dir}")


    processed = 0
    succeeded = []
    failed: dict[str, str] = {}
    schema_written_paths: list[str] = []
    # 不再进行 .xls -> .xlsx 的自动转换，也不删除原始 .xls

    for file_name in tqdm(os.listdir(excel_file_outer_dir)):
        lower_name = file_name.lower()
        if not (lower_name.endswith('.xlsx') or lower_name.endswith('.xls')):
            continue
        full_path = os.path.join(excel_file_outer_dir, file_name)
        try:
            file_size = os.path.getsize(full_path)
        except Exception:
            file_size = -1
        logger.info(f"开始处理: path={full_path}, size={file_size} bytes")
        try:
            df = _read_excel_with_fallbacks(full_path, file_name)
            logger.info(f"读取完成: {file_name}, shape={getattr(df, 'shape', None)}")
            
            # 计算文件内容的哈希值，确保唯一性
            file_content = df.to_string()
            file_content_hash = hashlib.md5(file_content.encode('utf-8')).hexdigest()
            
            df_convert = df.apply(infer_and_convert)
            df_convert = transfer_df_columns(df_convert)
            logger.info(f"列清洗完成: {file_name}, columns_count={len(df_convert.columns)}, columns={list(df_convert.columns)}")

            # 直接使用原始文件名作为后续 schema/表名依据（不再转换为 .xlsx）
            canonical_filename = file_name

            schema_dict, table_name = generate_schema_info(df_convert, canonical_filename, file_content_hash)
            logger.info(f"生成 schema 信息: table_name={table_name}, columns={len(schema_dict.get('column_list', []))}")

            schema_path = f"{SCHEMA_DIR}/{table_name}.json"
            try:
                with open(schema_path, 'w', encoding='utf-8') as f:
                    json.dump(schema_dict, f, ensure_ascii=False)
                # 写入后校验文件是否存在且非空
                exists = os.path.exists(schema_path)
                size = os.path.getsize(schema_path) if exists else 0
                if not exists or size == 0:
                    raise IOError(f"schema 文件校验失败: exists={exists}, size={size}")
                logger.info(f"Schema 已写入: {schema_path}, size={size} bytes")
                schema_written_paths.append(os.path.abspath(schema_path))
            except Exception as write_err:
                raise RuntimeError(f"写入 schema 失败: path={schema_path}, error={write_err}")
            
            # 插入数据库
            sql_alchemy_helper.insert_dataframe_batch(df_convert, table_name)
            logger.info(f"数据库写入完成: table={table_name}, rows={len(df_convert)}")

            succeeded.append(canonical_filename)
            processed += 1
        except Exception as e:
            failed[file_name] = str(e)
            logger.exception(f"处理失败: file={file_name}, error={e}")
            processed += 1
            # 不中断，继续处理其他文件
            continue

    summary = {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "schema_dir": SCHEMA_DIR,
        "excel_dir": excel_file_outer_dir,
        "schema_written": schema_written_paths,
    }
    logger.info(f"导入完成: {json.dumps(summary, ensure_ascii=False)}")
    return summary


if __name__ == "__main__":
    # 使用相对于项目根目录的正确路径
    excel_dir = os.path.join(PROJECT_ROOT, 'dataset', 'dev_excel')
    parse_excel_file_and_insert_to_db(excel_dir)

