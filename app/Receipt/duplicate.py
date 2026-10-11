import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.common.models import DuplicateCandidate, Receipt


COMPARABLE_STATUSES = ("REVIEWING", "APPROVED", "SETTLED")
DUPLICATE_THRESHOLD = 0.8


def _normalize_merchant_name(value: str) -> str:
    """상호명 비교 시 공백, 특수문자, 영문 대소문자를 정규화한다."""

    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def clear_duplicate_candidates(db: Session, receipt_id: int) -> None:
    """대상 영수증과 관련된 양방향 후보를 삭제한다."""

    db.execute(
        delete(DuplicateCandidate).where(
            (DuplicateCandidate.receipt_id == receipt_id)
            | (DuplicateCandidate.candidate_receipt_id == receipt_id)
        )
    )


def generate_duplicate_candidates(db: Session, receipt_id: int) -> None:
    """관리자 확정값을 기준으로 중복 후보를 재생성한다."""

    clear_duplicate_candidates(db, receipt_id)
    receipt = db.get(Receipt, receipt_id)
    if (
        receipt is None
        or receipt.status not in COMPARABLE_STATUSES
        or receipt.merchant_name is None
        or receipt.paid_at is None
        or receipt.amount is None
    ):
        return

    comparable = db.scalars(
        select(Receipt).where(
            Receipt.id != receipt.id,
            Receipt.status.in_(COMPARABLE_STATUSES),
            Receipt.merchant_name.is_not(None),
            Receipt.paid_at.is_not(None),
            Receipt.amount.is_not(None),
        )
    ).all()
    normalized_name = _normalize_merchant_name(receipt.merchant_name)

    for candidate in comparable:
        score = 0.0
        reasons: list[str] = []
        if receipt.amount == candidate.amount:
            score += 0.5
            reasons.append("금액 일치")
        if receipt.paid_at == candidate.paid_at:
            score += 0.3
            reasons.append("결제일 일치")
        if normalized_name == _normalize_merchant_name(candidate.merchant_name):
            score += 0.2
            reasons.append("상호명 일치")

        if score < DUPLICATE_THRESHOLD:
            continue

        match_reason = ", ".join(reasons)
        db.add(
            DuplicateCandidate(
                receipt_id=receipt.id,
                candidate_receipt_id=candidate.id,
                match_reason=match_reason,
                score=score,
            )
        )
        db.add(
            DuplicateCandidate(
                receipt_id=candidate.id,
                candidate_receipt_id=receipt.id,
                match_reason=match_reason,
                score=score,
            )
        )
