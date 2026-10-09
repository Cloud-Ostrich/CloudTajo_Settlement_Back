from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.Receipt.ocr import process_ocr_job
from app.Receipt.storage import ObjectStorage, StorageError, receipt_object_key
from app.User.dependencies import get_current_user, require_admin, require_user
from app.common.database import SessionLocal, get_db
from app.common.errors import raise_api_error
from app.common.models import (
    Category, DuplicateCandidate, OcrResult, Receipt, ReceiptFile, ReceiptHistory, Settlement, User,
)

router = APIRouter(prefix="/api", tags=["영수증"])
storage = ObjectStorage()


class OcrEditRequest(BaseModel):
    merchantName: str | None = Field(default=None, max_length=200)
    paidAt: date | None = None
    amount: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class ApproveRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class RejectRequest(BaseModel):
    rejectReason: str = Field(min_length=1, max_length=1000)


class SettleRequest(BaseModel):
    settledAt: datetime
    comment: str | None = Field(default=None, max_length=1000)


def _receipt_data(receipt: Receipt, file: ReceiptFile | None, ocr: OcrResult | None) -> dict[str, Any]:
    file_data = None
    if file is not None:
        try:
            file_url = storage.presigned_get_url(file.object_key)
        except StorageError as error:
            raise_api_error(str(error), "FILE_ACCESS_FAILED", 502)
        file_data = {
            "id": file.id,
            "originalFilename": file.original_filename,
            "contentType": file.content_type,
            "fileSize": file.file_size,
            "url": file_url,
        }
    ocr_data = None
    if ocr is not None:
        ocr_data = {
            "id": ocr.id,
            "status": ocr.status,
            "provider": ocr.provider,
            "merchantNameRaw": ocr.merchant_name_raw,
            "paidAtRaw": ocr.paid_at_raw,
            "amountRaw": int(ocr.amount_raw) if ocr.amount_raw is not None else None,
            "confidence": float(ocr.confidence) if ocr.confidence is not None else None,
            "rawPayload": ocr.raw_payload,
        }
    return {
        "id": receipt.id,
        "submitterId": receipt.submitter_id,
        "categoryId": receipt.category_id,
        "purpose": receipt.purpose,
        "status": receipt.status,
        "merchantName": receipt.merchant_name,
        "paidAt": receipt.paid_at,
        "amount": int(receipt.amount) if receipt.amount is not None else None,
        "memo": receipt.memo,
        "submittedAt": receipt.submitted_at,
        "file": file_data,
        "ocrResult": ocr_data,
    }


def _find_receipt(db: Session, receipt_id: int) -> Receipt:
    receipt = db.get(Receipt, receipt_id)
    if receipt is None:
        raise_api_error("영수증을 찾을 수 없습니다.", "RECEIPT_NOT_FOUND", 404)
    return receipt


def _history(db: Session, receipt_id: int, actor_id: int | None, action: str, **kwargs: Any) -> None:
    db.add(ReceiptHistory(receipt_id=receipt_id, actor_id=actor_id, action=action, **kwargs))


@router.post("/receipts", status_code=status.HTTP_201_CREATED, summary="영수증 제출 및 OCR 요청")
async def create_receipt(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    purpose: str = Form(..., min_length=1, max_length=200),
    categoryId: int = Form(...),
    memo: str | None = Form(default=None),
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    category = db.get(Category, categoryId)
    if category is None or not category.active:
        raise_api_error("활성 카테고리를 찾을 수 없습니다.", "INVALID_REQUEST", 400)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise_api_error("이미지 파일만 업로드할 수 있습니다.", "FILE_UPLOAD_FAILED", 400)
    content = await image.read()
    receipt = Receipt(submitter_id=current_user.id, category_id=categoryId, purpose=purpose, memo=memo)
    db.add(receipt)
    db.flush()
    object_key = receipt_object_key(receipt.id, image.filename or "receipt.bin")
    try:
        storage.put(object_key, content, image.content_type)
    except StorageError as error:
        db.rollback()
        raise_api_error(str(error), "FILE_UPLOAD_FAILED", 502)
    db.add(ReceiptFile(receipt_id=receipt.id, object_key=object_key, original_filename=image.filename or "receipt.bin", content_type=image.content_type, file_size=len(content)))
    _history(db, receipt.id, current_user.id, "SUBMIT", to_status="SUBMITTED")
    ocr = OcrResult(receipt_id=receipt.id, status="OCR_PENDING")
    db.add(ocr)
    db.flush()
    _history(db, receipt.id, None, "OCR_PENDING", snapshot={"ocrResultId": ocr.id})
    db.commit()
    background_tasks.add_task(process_ocr_job, ocr.id, SessionLocal)
    return {"success": True, "message": "영수증 제출이 접수되었습니다.", "data": {"receiptId": receipt.id, "status": receipt.status, "ocrStatus": ocr.status}}


@router.get("/receipts/my", summary="내 영수증 목록 조회")
def list_my_receipts(status_filter: str | None = Query(default=None, alias="status"), page: int = 0, size: int = 20, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if page < 0 or size < 1 or size > 100:
        raise_api_error("page와 size가 올바르지 않습니다.", "INVALID_REQUEST", 400)
    query = select(Receipt).where(Receipt.submitter_id == current_user.id)
    count_query = select(func.count()).select_from(Receipt).where(Receipt.submitter_id == current_user.id)
    if status_filter:
        query = query.where(Receipt.status == status_filter)
        count_query = count_query.where(Receipt.status == status_filter)
    total = db.scalar(count_query) or 0
    rows = list(db.scalars(query.order_by(Receipt.id.desc()).offset(page * size).limit(size)).all())
    items = [{"id": r.id, "purpose": r.purpose, "categoryId": r.category_id, "status": r.status, "merchantName": r.merchant_name, "paidAt": r.paid_at, "amount": int(r.amount) if r.amount is not None else None, "submittedAt": r.submitted_at} for r in rows]
    return {"success": True, "message": "내 영수증 목록 조회에 성공했습니다.", "data": {"items": items, "page": page, "size": size, "totalElements": total, "totalPages": (total + size - 1) // size}}


@router.get("/receipts/{receipt_id}", summary="영수증 상세 조회")
def get_receipt(receipt_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    receipt = _find_receipt(db, receipt_id)
    if receipt.submitter_id != current_user.id and current_user.role != "ADMIN":
        raise_api_error("영수증을 조회할 권한이 없습니다.", "FORBIDDEN_ROLE", 403)
    file = db.scalar(select(ReceiptFile).where(ReceiptFile.receipt_id == receipt.id))
    ocr = db.scalar(select(OcrResult).where(OcrResult.receipt_id == receipt.id, OcrResult.selected.is_(True)).order_by(OcrResult.id.desc()))
    if ocr is None:
        ocr = db.scalar(select(OcrResult).where(OcrResult.receipt_id == receipt.id).order_by(OcrResult.id.desc()))
    return {"success": True, "message": "영수증 상세 조회에 성공했습니다.", "data": _receipt_data(receipt, file, ocr)}


@router.post("/receipts/{receipt_id}/ocr/retry", summary="OCR 재요청")
def retry_ocr(receipt_id: int, background_tasks: BackgroundTasks, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    receipt = _find_receipt(db, receipt_id)
    if receipt.status == "SETTLED":
        raise_api_error("정산 완료된 영수증은 OCR을 재요청할 수 없습니다.", "INVALID_STATUS_TRANSITION", 409)
    ocr = OcrResult(receipt_id=receipt.id, status="OCR_PENDING")
    db.add(ocr)
    db.flush()
    _history(db, receipt.id, current_user.id, "OCR_RETRY", snapshot={"ocrResultId": ocr.id})
    db.commit()
    background_tasks.add_task(process_ocr_job, ocr.id, SessionLocal)
    return {"success": True, "message": "OCR 재요청이 접수되었습니다.", "data": {"receiptId": receipt.id, "ocrStatus": ocr.status}}


@router.patch("/admin/receipts/{receipt_id}/ocr", summary="OCR 추출값 수정 및 확정")
def edit_ocr(receipt_id: int, payload: OcrEditRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    receipt = _find_receipt(db, receipt_id)
    if receipt.status in {"APPROVED", "SETTLED"}:
        raise_api_error("승인 또는 정산 완료된 영수증은 수정할 수 없습니다.", "INVALID_STATUS_TRANSITION", 409)
    before = {
        "merchantName": receipt.merchant_name,
        "paidAt": receipt.paid_at.isoformat() if receipt.paid_at else None,
        "amount": int(receipt.amount) if receipt.amount is not None else None,
    }
    receipt.merchant_name, receipt.paid_at, receipt.amount = payload.merchantName, payload.paidAt, payload.amount
    _history(db, receipt.id, current_user.id, "EDIT_OCR", reason=payload.reason, snapshot={"before": before, "after": payload.model_dump(mode="json")})
    if receipt.status == "SUBMITTED":
        old = receipt.status
        receipt.status = "REVIEWING"
        _history(db, receipt.id, current_user.id, "REVIEW", from_status=old, to_status=receipt.status)
    db.commit()
    return {"success": True, "message": "확정값을 저장했습니다.", "data": {"receiptId": receipt.id, "status": receipt.status}}


@router.post("/admin/receipts/{receipt_id}/approve", summary="영수증 승인")
def approve(receipt_id: int, payload: ApproveRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _change_review_status(receipt_id, "APPROVED", current_user, db, payload.comment, "APPROVE")


@router.post("/admin/receipts/{receipt_id}/reject", summary="영수증 반려")
def reject(receipt_id: int, payload: RejectRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _change_review_status(receipt_id, "REJECTED", current_user, db, payload.rejectReason, "REJECT")


def _change_review_status(receipt_id: int, new_status: str, user: User, db: Session, reason: str | None, action: str) -> dict[str, Any]:
    receipt = _find_receipt(db, receipt_id)
    if receipt.status != "REVIEWING":
        raise_api_error("검토 중인 영수증만 처리할 수 있습니다.", "INVALID_STATUS_TRANSITION", 409)
    old = receipt.status
    receipt.status = new_status
    receipt.reviewed_at = datetime.now()
    _history(db, receipt.id, user.id, action, from_status=old, to_status=new_status, reason=reason)
    db.commit()
    return {"success": True, "message": "영수증 상태를 변경했습니다.", "data": {"receiptId": receipt.id, "status": receipt.status}}


@router.post("/admin/receipts/{receipt_id}/settle", summary="정산 완료 처리")
def settle(receipt_id: int, payload: SettleRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    receipt = _find_receipt(db, receipt_id)
    if receipt.status != "APPROVED":
        raise_api_error("승인된 영수증만 정산할 수 있습니다.", "INVALID_STATUS_TRANSITION", 409)
    receipt.status = "SETTLED"
    db.add(Settlement(receipt_id=receipt.id, settled_by=current_user.id, settled_at=payload.settledAt, comment=payload.comment))
    _history(db, receipt.id, current_user.id, "SETTLE", from_status="APPROVED", to_status="SETTLED", reason=payload.comment)
    db.commit()
    return {"success": True, "message": "정산 처리가 완료되었습니다.", "data": {"receiptId": receipt.id, "status": receipt.status}}


@router.get("/admin/receipts", summary="관리자 영수증 목록 조회")
def list_admin_receipts(status_filter: str | None = Query(default=None, alias="status"), categoryId: int | None = None, from_date: date | None = Query(default=None, alias="from"), to_date: date | None = Query(default=None, alias="to"), page: int = 0, size: int = 20, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    if page < 0 or size < 1 or size > 100:
        raise_api_error("page와 size가 올바르지 않습니다.", "INVALID_REQUEST", 400)
    query = select(Receipt)
    count_query = select(func.count()).select_from(Receipt)
    filters = []
    if status_filter:
        filters.append(Receipt.status == status_filter)
    if categoryId is not None:
        filters.append(Receipt.category_id == categoryId)
    if from_date is not None:
        filters.append(Receipt.paid_at >= from_date)
    if to_date is not None:
        filters.append(Receipt.paid_at <= to_date)
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)
    total = db.scalar(count_query) or 0
    rows = list(db.scalars(query.order_by(Receipt.id.desc()).offset(page * size).limit(size)).all())
    items = [{"id": r.id, "submitterId": r.submitter_id, "categoryId": r.category_id, "purpose": r.purpose, "status": r.status, "merchantName": r.merchant_name, "paidAt": r.paid_at, "amount": int(r.amount) if r.amount is not None else None, "submittedAt": r.submitted_at} for r in rows]
    return {"success": True, "message": "관리자 영수증 목록 조회에 성공했습니다.", "data": {"items": items, "page": page, "size": size, "totalElements": total, "totalPages": (total + size - 1) // size}}


@router.post("/receipts/{receipt_id}/resubmit", summary="반려 영수증 재제출")
async def resubmit(receipt_id: int, background_tasks: BackgroundTasks, image: UploadFile = File(...), purpose: str = Form(...), categoryId: int = Form(...), memo: str | None = Form(default=None), current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    receipt = _find_receipt(db, receipt_id)
    if receipt.submitter_id != current_user.id or receipt.status != "REJECTED":
        raise_api_error("반려된 본인 영수증만 재제출할 수 있습니다.", "INVALID_STATUS_TRANSITION", 409)
    category = db.get(Category, categoryId)
    if category is None or not category.active:
        raise_api_error("활성 카테고리를 찾을 수 없습니다.", "INVALID_REQUEST", 400)
    content = await image.read()
    old_file = db.scalar(select(ReceiptFile).where(ReceiptFile.receipt_id == receipt.id))
    old_object_key = old_file.object_key if old_file else None
    object_key = receipt_object_key(receipt.id, image.filename or "receipt.bin")
    try:
        storage.put(object_key, content, image.content_type or "application/octet-stream")
    except StorageError as error:
        raise_api_error(str(error), "FILE_UPLOAD_FAILED", 502)
    if old_file:
        old_file.object_key = object_key
        old_file.original_filename = image.filename or "receipt.bin"
        old_file.content_type = image.content_type or "application/octet-stream"
        old_file.file_size = len(content)
        if old_object_key and old_object_key != object_key:
            try:
                storage.delete(old_object_key)
            except StorageError:
                pass
    receipt.purpose, receipt.category_id, receipt.memo, receipt.status = purpose, categoryId, memo, "SUBMITTED"
    _history(db, receipt.id, current_user.id, "SUBMIT", from_status="REJECTED", to_status="SUBMITTED")
    ocr = OcrResult(receipt_id=receipt.id, status="OCR_PENDING")
    db.add(ocr)
    db.flush()
    db.commit()
    background_tasks.add_task(process_ocr_job, ocr.id, SessionLocal)
    return {"success": True, "message": "재제출이 접수되었습니다.", "data": {"receiptId": receipt.id, "status": receipt.status, "ocrStatus": ocr.status}}


@router.get("/receipts/{receipt_id}/histories", summary="영수증 처리 이력 조회")
def histories(receipt_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    receipt = _find_receipt(db, receipt_id)
    if receipt.submitter_id != current_user.id and current_user.role != "ADMIN":
        raise_api_error("이력을 조회할 권한이 없습니다.", "FORBIDDEN_ROLE", 403)
    rows = db.scalars(select(ReceiptHistory).where(ReceiptHistory.receipt_id == receipt_id).order_by(ReceiptHistory.id)).all()
    data = [{"id": h.id, "actorId": h.actor_id, "action": h.action, "fromStatus": h.from_status, "toStatus": h.to_status, "reason": h.reason, "snapshot": h.snapshot, "createdAt": h.created_at} for h in rows]
    return {"success": True, "message": "처리 이력 조회에 성공했습니다.", "data": data}


@router.get("/admin/receipts/{receipt_id}/duplicates", summary="중복 후보 조회")
def duplicates(receipt_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    _find_receipt(db, receipt_id)
    rows = db.scalars(select(DuplicateCandidate).where(DuplicateCandidate.receipt_id == receipt_id).order_by(DuplicateCandidate.id)).all()
    data = [{"candidateReceiptId": row.candidate_receipt_id, "matchReason": row.match_reason, "score": float(row.score) if row.score is not None else None} for row in rows]
    return {"success": True, "message": "중복 후보 조회에 성공했습니다.", "data": data}


@router.get("/admin/dashboard/summary", summary="운영 대시보드 요약 조회")
def dashboard_summary(month: str, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        year, month_number = (int(part) for part in month.split("-"))
        month_start = date(year, month_number, 1)
        month_end = date(year + (month_number == 12), 1 if month_number == 12 else month_number + 1, 1)
    except (ValueError, TypeError):
        raise_api_error("month는 YYYY-MM 형식이어야 합니다.", "INVALID_REQUEST", 400)
    base = select(Receipt).where(Receipt.paid_at >= month_start, Receipt.paid_at < month_end)
    rows = list(db.scalars(base).all())
    categories = {category.id: category.name for category in db.scalars(select(Category)).all()}
    paid_rows = [row for row in rows if row.status in {"APPROVED", "SETTLED"} and row.amount is not None]
    category_summaries: dict[int, dict[str, Any]] = {}
    for row in paid_rows:
        item = category_summaries.setdefault(row.category_id, {"categoryId": row.category_id, "categoryName": categories.get(row.category_id), "amount": 0, "count": 0})
        item["amount"] += int(row.amount)
        item["count"] += 1
    reviewed = [row for row in rows if row.reviewed_at is not None]
    average_review = (sum((row.reviewed_at - row.submitted_at).total_seconds() / 60 for row in reviewed) / len(reviewed)) if reviewed else 0
    data = {"month": month, "totalAmount": sum(int(row.amount) for row in paid_rows), "categorySummaries": list(category_summaries.values()), "pendingCount": sum(row.status in {"SUBMITTED", "REVIEWING"} for row in rows), "rejectedCount": sum(row.status == "REJECTED" for row in rows), "averageReviewMinutes": average_review}
    return {"success": True, "message": "대시보드 요약 조회에 성공했습니다.", "data": data}
