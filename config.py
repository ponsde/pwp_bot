from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
SAMPLE_DIR = DATA_DIR / "sample" / "示例数据"
REPORTS_DIR = SAMPLE_DIR / "附件2：财务报告"
SCHEMA_XLSX = SAMPLE_DIR / "附件3：数据库-表名及字段说明.xlsx"
COMPANY_XLSX = SAMPLE_DIR / "附件1：中药上市公司基本信息（截至到2025年12月22日）.xlsx"
DEFAULT_DB_PATH = DATA_DIR / "db" / "financial_reports.db"
RESEARCH_DIR = SAMPLE_DIR / "附件5：研报数据"
RESEARCH_QUESTIONS_XLSX = SAMPLE_DIR / "附件6：问题汇总.xlsx"
OV_DATA_DIR = ROOT_DIR / ".openviking"
OV_CONFIG_PATH = ROOT_DIR / "ov.conf"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class Settings:
    llm_api_key: str
    llm_api_base: str
    llm_model: str
    embedding_api_key: str
    embedding_api_base: str
    embedding_model: str
    llm_timeout: int
    sqlite_db_path: Path


def load_settings(require_llm_api_key: bool = False) -> Settings:
    load_dotenv(ROOT_DIR / ".env")

    llm_api_key = os.getenv("LLM_API_KEY", "").strip()
    llm_api_base = os.getenv("LLM_API_BASE", "").strip()
    llm_model = os.getenv("LLM_MODEL", "").strip()
    embedding_api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
    embedding_api_base = os.getenv("EMBEDDING_API_BASE", "").strip()
    embedding_model = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()
    llm_timeout = int(os.getenv("LLM_TIMEOUT", "60"))
    sqlite_db_path = Path(os.getenv("SQLITE_DB_PATH", str(DEFAULT_DB_PATH)))
    if not sqlite_db_path.is_absolute():
        sqlite_db_path = ROOT_DIR / sqlite_db_path

    if require_llm_api_key and not llm_api_key:
        raise RuntimeError("Missing LLM_API_KEY. Copy .env.example to .env and fill it.")
    if not llm_api_base:
        raise RuntimeError("Missing LLM_API_BASE. Set it in your environment.")
    if not llm_model:
        raise RuntimeError("Missing LLM_MODEL. Set it in your environment.")
    if not embedding_model:
        raise RuntimeError("Missing EMBEDDING_MODEL.")

    if not SCHEMA_XLSX.exists():
        raise RuntimeError(f"Schema file not found: {SCHEMA_XLSX}")
    if not COMPANY_XLSX.exists():
        raise RuntimeError(f"Company file not found: {COMPANY_XLSX}")

    sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        llm_api_key=llm_api_key,
        llm_api_base=llm_api_base,
        llm_model=llm_model,
        embedding_api_key=embedding_api_key,
        embedding_api_base=embedding_api_base,
        embedding_model=embedding_model,
        llm_timeout=llm_timeout,
        sqlite_db_path=sqlite_db_path,
    )
