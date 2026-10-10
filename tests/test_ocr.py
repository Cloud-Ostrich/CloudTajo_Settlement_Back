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


def test_parse_delivery_order_text() -> None:
    payload = {
        "images": [{
            "fields": [
                {"inferText": "주문매장: 베빗쿠키 ()"},
                {"inferText": "총결제금액 19,300"},
                {"inferText": "주문시간: 2026-10-10 12:10:00 PM"},
            ]
        }]
    }

    assert parse_receipt_fields(payload) == {
        "merchantName": "베빗쿠키 ()",
        "paidAt": date(2026, 10, 10),
        "amount": 19300,
    }


def test_parse_pos_receipt_text_with_spaced_total_label() -> None:
    payload = {
        "images": [{
            "fields": [
                {"inferText": "상호 두부랑놀개 대표 김한솔"},
                {"inferText": "승인일시 2026-10-10 16:21:49"},
                {"inferText": "결제금액 19,000"},
            ]
        }]
    }

    assert parse_receipt_fields(payload) == {
        "merchantName": "두부랑놀개",
        "paidAt": date(2026, 10, 10),
        "amount": 19000,
    }


def test_parse_gs_receipt_total_amount() -> None:
    payload = {
        "images": [{
            "fields": [
                {"inferText": "GS25영통방죽점"},
                {"inferText": "2026/10/10(토)"},
                {"inferText": "합계수량/금액 1 2,300 2,300"},
            ]
        }]
    }

    assert parse_receipt_fields(payload) == {
        "merchantName": None,
        "paidAt": None,
        "amount": 2300,
    }
