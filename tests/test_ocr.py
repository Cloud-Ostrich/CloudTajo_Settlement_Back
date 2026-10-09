from datetime import date

from app.Receipt.ocr import parse_receipt_fields


def test_parse_receipt_fields_from_clova_receipt_response() -> None:
    payload = {
        "images": [
            {
                "receipt": {
                    "result": {
                        "storeInfo": {"name": {"text": "구름식당"}},
                        "paymentInfo": {
                            "date": {
                                "formatted": {"year": "2026", "month": "10", "day": "9"}
                            }
                        },
                        "totalPrice": {
                            "creditCardPrice": {"formatted": {"value": "18,900"}}
                        },
                    }
                }
            }
        ]
    }

    assert parse_receipt_fields(payload) == {
        "merchantName": "구름식당",
        "paidAt": date(2026, 10, 9),
        "amount": 18900,
    }


def test_parse_receipt_fields_returns_null_candidates_when_receipt_result_is_missing() -> None:
    assert parse_receipt_fields({"images": [{"inferResult": "SUCCESS", "fields": []}]}) == {
        "merchantName": None,
        "paidAt": None,
        "amount": None,
    }


def test_parse_receipt_fields_from_general_ocr_text() -> None:
    payload = {
        "images": [
            {
                "fields": [
                    {"inferText": "가맹점명: 보소다테점"},
                    {"inferText": "대표자명: 멘마짱"},
                    {"inferText": "승인금액: 100,000"},
                    {"inferText": "거래일시: 17-07-05 T09:35"},
                ]
            }
        ]
    }

    assert parse_receipt_fields(payload) == {
        "merchantName": "보소다테점",
        "paidAt": date(2017, 7, 5),
        "amount": 100000,
    }
