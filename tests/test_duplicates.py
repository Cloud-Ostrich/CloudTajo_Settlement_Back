from datetime import date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.Receipt.duplicate import generate_duplicate_candidates
from app.common.database import Base
from app.common.models import Category, DuplicateCandidate, Receipt, User


def test_duplicate_candidates_are_generated_in_both_directions() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(User(id=1, name="사용자", email="duplicate@example.com", password_hash="x", role="USER"))
        db.add(Category(id=1, name="식비", active=True))
        db.commit()

        first = Receipt(
            submitter_id=1,
            category_id=1,
            purpose="첫 지출",
            status="REVIEWING",
            merchant_name="스타벅스 강남점",
            paid_at=date(2026, 10, 10),
            amount=5000,
            submitted_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(first)
        db.commit()
        generate_duplicate_candidates(db, first.id)
        db.commit()
        assert db.scalars(select(DuplicateCandidate)).all() == []

        second = Receipt(
            submitter_id=1,
            category_id=1,
            purpose="두 번째 지출",
            status="REVIEWING",
            merchant_name="스타벅스강남점",
            paid_at=date(2026, 10, 10),
            amount=5000,
            submitted_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(second)
        db.commit()
        generate_duplicate_candidates(db, second.id)
        db.commit()

        pairs = {
            (row.receipt_id, row.candidate_receipt_id)
            for row in db.scalars(select(DuplicateCandidate)).all()
        }
        assert pairs == {(first.id, second.id), (second.id, first.id)}


def test_duplicate_candidates_are_rebuilt_when_confirmed_value_changes() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add(User(id=1, name="사용자", email="rebuild@example.com", password_hash="x", role="USER"))
        db.add(Category(id=1, name="교통비", active=True))
        db.commit()
        receipts = [
            Receipt(
                submitter_id=1,
                category_id=1,
                purpose="지출",
                status="REVIEWING",
                merchant_name="택시",
                paid_at=date(2026, 10, 11),
                amount=10000,
                submitted_at=datetime.now(),
                updated_at=datetime.now(),
            ),
            Receipt(
                submitter_id=1,
                category_id=1,
                purpose="지출 재제출",
                status="REVIEWING",
                merchant_name="택시",
                paid_at=date(2026, 10, 11),
                amount=10000,
                submitted_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]
        db.add_all(receipts)
        db.commit()

        generate_duplicate_candidates(db, receipts[1].id)
        db.commit()
        receipts[1].amount = 12000
        generate_duplicate_candidates(db, receipts[1].id)
        db.commit()

        assert db.scalars(select(DuplicateCandidate)).all() == []
