import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"필수 환경변수 {name}이(가) 설정되지 않았습니다.")
    return value


def build_database_url() -> URL:
    try:
        port = int(_required_env("DB_PORT"))
    except ValueError as error:
        raise RuntimeError("DB_PORT는 숫자여야 합니다.") from error

    return URL.create(
        drivername="mysql+pymysql",
        username=_required_env("DB_USER"),
        password=_required_env("DB_PASSWORD"),
        host=_required_env("DB_HOST"),
        port=port,
        database=_required_env("DB_NAME"),
    )


DATABASE_URL = build_database_url()
engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> None:
    """DB 연결 가능 여부를 확인하고 실패 시 예외를 그대로 전달한다."""

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
