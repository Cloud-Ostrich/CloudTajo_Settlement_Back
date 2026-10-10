import json
import os
import re
import uuid
from datetime import date, datetime, timezone
from urllib import error, request

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.models import OcrResult, Receipt, ReceiptFile, ReceiptHistory
from app.common.time import utc_now
from app.Receipt.storage import ObjectStorage, StorageError


class OcrProviderError(RuntimeError):
    pass


def call_clova_ocr(content: bytes, filename: str, content_type: str) -> dict:
    url = os.getenv("CLOVA_OCR_API_URL")
    secret = os.getenv("CLOVA_OCR_SECRET")
    if not url or not secret:
        raise OcrProviderError("CLOVA OCR 설정이 없습니다.")
    boundary = f"----CloudTajo{uuid.uuid4().hex}"
    message = json.dumps({"version": "V2", "requestId": str(uuid.uuid4()), "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000), "images": [{"format": filename.rsplit(".", 1)[-1].lower(), "name": filename}]})
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


def _recognized_value(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    formatted = value.get("formatted")
    if isinstance(formatted, dict) and formatted.get("value") is not None:
        return str(formatted["value"]).strip() or None
    text = value.get("text")
    return str(text).strip() if text is not None and str(text).strip() else None


def _recognized_date(value: object) -> date | None:
    if not isinstance(value, dict):
        return None
    formatted = value.get("formatted")
    if isinstance(formatted, dict):
        try:
            return date(
                int(formatted["year"]),
                int(formatted["month"]),
                int(formatted["day"]),
            )
        except (KeyError, TypeError, ValueError):
            pass
    text = _recognized_value(value)
    if text is None:
        return None
    match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", text)
    if match is None:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def _recognized_amount(value: object) -> int | None:
    text = _recognized_value(value)
    if text is None:
        return None
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None


def _parse_general_receipt_fields(raw_text: str) -> dict[str, object | None]:
    def _date_from_match(match: re.Match[str] | None) -> date | None:
        if match is None:
            return None
        year, month, day = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None

    merchant_match = re.search(
        r"(?:가맹점명|상호|주문매장|매장)\s*[:：]?\s*(.+?)"
        r"(?=\s+(?:대표자명|대표|사업자\s*번호|사업자등록번호|전화번호|대표번호|"
        r"주\s*소|주소|주문시간|주문일시|판매시간|결제일시|승인일시|"
        r"승인금액|합계금액|결제금액|총\s*결제\s*금액|총액|합\s*계|$))",
        raw_text,
    )
    merchant_name = merchant_match.group(1).strip() if merchant_match else None

    date_pattern = r"(\d{2,4})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})"
    paid_at = None
    for label in ("거래일시", "승인일시", "주문시간", "주문일시", "판매시간", "결제일시"):
        date_match = re.search(rf"{label}\s*[:：]?\s*{date_pattern}", raw_text)
        paid_at = _date_from_match(date_match)
        if paid_at is not None:
            break
    if paid_at is None:
        compact_date = re.search(r"(?:거래일시|승인일시|주문시간|주문일시|판매시간|결제일시)\s*[:：]?\s*(\d{4})(\d{2})(\d{2})", raw_text)
        paid_at = _date_from_match(compact_date)

    amount_match = re.search(
        r"(?:승인금액|합계금액|결제금액|총\s*결제\s*금액|총액|합\s*계)"
        r"\s*\]?\s*[:：]?\s*([\d,]+)",
        raw_text,
    )
    if amount_match is not None:
        amount = int(amount_match.group(1).replace(",", ""))
    else:
        total_match = re.search(r"합계수량\s*/\s*금액\s+\d+\s+[\d,]+\s+([\d,]+)", raw_text)
        amount = int(total_match.group(1).replace(",", "")) if total_match else None
    return {"merchantName": merchant_name, "paidAt": paid_at, "amount": amount}


def parse_receipt_fields(payload: dict) -> dict[str, object | None]:
    """Extract receipt candidates without writing them to confirmed receipt fields."""
    image = payload.get("images", [{}])[0]
    result = image.get("receipt", {}).get("result", {})
    if not isinstance(result, dict):
        return _parse_general_receipt_fields(_raw_text(payload))

    store_info = result.get("storeInfo", {})
    payment_info = result.get("paymentInfo", {})
    total_price = result.get("totalPrice", {})
    merchant_name = _recognized_value(store_info.get("name")) if isinstance(store_info, dict) else None
    paid_at = _recognized_date(payment_info.get("date")) if isinstance(payment_info, dict) else None
    amount = None
    if isinstance(total_price, dict):
        amount = _recognized_amount(total_price.get("creditCardPrice"))
        if amount is None:
            amount = _recognized_amount(total_price.get("price"))
    parsed = {"merchantName": merchant_name, "paidAt": paid_at, "amount": amount}
    fallback = _parse_general_receipt_fields(_raw_text(payload))
    return {key: value if value is not None else fallback[key] for key, value in parsed.items()}


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
            parsed = parse_receipt_fields(payload)
            result.merchant_name_raw = parsed["merchantName"]
            result.paid_at_raw = parsed["paidAt"]
            result.amount_raw = parsed["amount"]
            result.parsed_payload = {
                "source": "CLOVA_OCR",
                "parserVersion": "receipt-v1",
                "fields": {
                    "merchantName": parsed["merchantName"],
                    "paidAt": parsed["paidAt"].isoformat() if parsed["paidAt"] else None,
                    "amount": parsed["amount"],
                },
            }
            receipt = db.get(Receipt, result.receipt_id)
            if receipt is not None and receipt.status == "SUBMITTED":
                old_status = receipt.status
                receipt.status = "REVIEWING"
                receipt.updated_at = utc_now()
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
            receipt.updated_at = utc_now()
        db.commit()
    finally:
        db.close()


def apply_mock_ocr_result(db: Session, result: OcrResult, merchant_name: str, paid_at: date, amount: int) -> None:
    """테스트에서 provider adapter를 대체하기 위한 작은 도우미."""
    result.status = "OCR_DONE"
    result.merchant_name_raw = merchant_name
    result.paid_at_raw = paid_at
    result.amount_raw = amount
