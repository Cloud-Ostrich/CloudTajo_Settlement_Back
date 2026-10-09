from datetime import datetime

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, JSON, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base
from app.common.time import utc_now


def id_column():
    """Use BIGINT in MySQL and an autoincrement-compatible INTEGER in SQLite tests."""

    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = id_column()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=utc_now,
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = id_column()
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = id_column()
    submitter_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUBMITTED", index=True)
    merchant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[int | None] = mapped_column(Numeric(15, 0), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=utc_now)


class ReceiptFile(Base):
    __tablename__ = "receipt_files"

    id: Mapped[int] = id_column()
    receipt_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class OcrResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[int] = id_column()
    receipt_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="CLOVA_OCR")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OCR_PENDING")
    merchant_name_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    paid_at_raw: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_raw: Mapped[int | None] = mapped_column(Numeric(15, 0), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class ReceiptHistory(Base):
    __tablename__ = "receipt_histories"

    id: Mapped[int] = id_column()
    receipt_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[int] = id_column()
    receipt_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    settled_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    settled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"

    id: Mapped[int] = id_column()
    receipt_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    candidate_receipt_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    match_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
