import json
import os
import uuid
from datetime import date, datetime
from urllib import error, request

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.models import OcrResult, Receipt, ReceiptFile, ReceiptHistory
from app.Receipt.storage import ObjectStorage, StorageError


class OcrProviderError(RuntimeError):
    pass


def call_clova_ocr(content: bytes, filename: str, content_type: str) -> dict:
    url = os.getenv("CLOVA_OCR_API_URL")
    secret = os.getenv("CLOVA_OCR_SECRET")
    if not url or not secret:
        raise OcrProviderError("CLOVA OCR 설정이 없습니다.")
    boundary = f"----CloudTajo{uuid.uuid4().hex}"
    message = json.dumps({"version": "V2", "requestId": str(uuid.uuid4()), "timestamp": int(datetime.now().timestamp() * 1000), "images": [{"format": filename.rsplit(".", 1)[-1].lower(), "name": filename}]})
    body = b"".join(
        [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"message\"\r\n\r\n{message}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode(),
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    req = request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-OCR-SECRET": secret}, method="POST")
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read())
    except error.HTTPError as http_error:
        response_body = http_error.read().decode("utf-8", errors="replace")[:300]
        raise OcrProviderError(f"CLOVA OCR HTTP {http_error.code}: {response_body}") from http_error
    except error.URLError as url_error:
        raise OcrProviderError(f"CLOVA OCR 네트워크 오류: {url_error.reason}") from url_error
    except Exception as request_error:
        raise OcrProviderError(f"CLOVA OCR 호출에 실패했습니다: {type(request_error).__name__}") from request_error


def _raw_text(payload: dict) -> str:
    fields = payload.get("images", [{}])[0].get("fields", [])
    return " ".join(str(field.get("inferText", "")) for field in fields).strip()


def process_ocr_job(ocr_result_id: int, session_factory) -> None:
    """OCR provider 연결 지점.

    CLOVA credentials/provider adapter가 연결되기 전에는 성공으로 처리하지 않는다.
    """
    db: Session = session_factory()
    try:
        result = db.get(OcrResult, ocr_result_id)
        if result is None:
            return
        file = db.scalar(select(ReceiptFile).where(ReceiptFile.receipt_id == result.receipt_id))
        try:
            if file is None:
                raise OcrProviderError("OCR 대상 파일을 찾을 수 없습니다.")
            payload = call_clova_ocr(ObjectStorage().get(file.object_key), file.original_filename, file.content_type)
            result.status = "OCR_DONE"
            result.raw_payload = payload
            result.raw_text = _raw_text(payload)
            result.parsed_payload = {"source": "CLOVA_OCR", "parserVersion": "raw-only-v1"}
            receipt = db.get(Receipt, result.receipt_id)
            if receipt is not None and receipt.status == "SUBMITTED":
                old_status = receipt.status
                receipt.status = "REVIEWING"
                receipt.updated_at = datetime.utcnow()
                db.add(ReceiptHistory(receipt_id=receipt.id, actor_id=None, action="REVIEW", from_status=old_status, to_status=receipt.status))
            db.add(ReceiptHistory(receipt_id=result.receipt_id, actor_id=None, action="OCR_DONE", snapshot={"ocrResultId": result.id, "status": result.status}))
            db.commit()
            return
        except (OcrProviderError, StorageError) as error:
            result.status = "OCR_FAILED"
            result.error_message = str(error)
        receipt = db.get(Receipt, result.receipt_id)
        db.add(
            ReceiptHistory(
                receipt_id=result.receipt_id,
                actor_id=None,
                action="OCR_FAILED",
                reason=result.error_message,
                snapshot={"ocrResultId": result.id, "status": result.status},
            )
        )
        if receipt is not None and receipt.status == "SUBMITTED":
            receipt.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def apply_mock_ocr_result(db: Session, result: OcrResult, merchant_name: str, paid_at: date, amount: int) -> None:
    """테스트에서 provider adapter를 대체하기 위한 작은 도우미."""
    result.status = "OCR_DONE"
    result.merchant_name_raw = merchant_name
    result.paid_at_raw = paid_at
    result.amount_raw = amount
