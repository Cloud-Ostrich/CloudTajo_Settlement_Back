# 구름타 조정산소 API Specification

> 목적: Codex 하네스가 API 라우팅, 요청·응답 필드, 권한, 상태 전이를 일관되게 구현하고 검증하기 위한 기준 문서입니다.
>
> 원본: `구름타조정산소_API_명세서.pdf`
>
> DB 기준: [`DB_SPEC.md`](./DB_SPEC.md)

## 1. 공통 규칙

| 항목 | 규칙 |
|---|---|
| Base URL | `/api` |
| 인증 | `Authorization: Bearer {accessToken}` |
| 일반 요청 | `application/json` |
| 파일 업로드 | `multipart/form-data` |
| 권한 | `USER` 일반 구성원, `ADMIN` 회계 관리자 |
| 성공 응답 | `success`, `message`, `data` |
| 실패 응답 | `success`, `message`, `errorCode` |

### 성공 응답

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {}
}
```

### 실패 응답

```json
{
  "success": false,
  "message": "에러 메시지",
  "errorCode": "ERROR_CODE"
}
```

모든 인증 필요 API는 Bearer 토큰을 검증한다. `password_hash` 또는 `passwordHash`는 어떤 API 응답에도 포함하지 않는다.
영수증 원본 이미지는 Object Storage에 비공개로 저장하며, 저장 키 prefix는 `receipts/{year}/{month}/`를 사용한다. 파일 접근 API는 영수증 소유자 또는 `ADMIN`인지 확인한 뒤 파일을 제공한다.

## 2. 상태 값과 권한

| 상태 | 의미 |
|---|---|
| `SUBMITTED` | 사용자가 영수증을 제출한 상태 |
| `REVIEWING` | 관리자가 검토 중인 상태 |
| `APPROVED` | 관리자가 승인한 상태 |
| `REJECTED` | 관리자가 반려한 상태 |
| `SETTLED` | 정산 완료 상태 |

허용 상태 전이:

```text
SUBMITTED -> REVIEWING
REVIEWING -> APPROVED -> SETTLED
REVIEWING -> REJECTED -> SUBMITTED  (재제출)
```

OCR 상태는 영수증 상태와 분리해 `ocr_results.status`에 저장한다.

```text
OCR_PENDING -> OCR_DONE
            -> OCR_FAILED
```

OCR 실패 시 `receipts.status`는 `SUBMITTED`로 유지한다. 재요청은 기존 `ocr_results`를 수정하거나 삭제하지 않고 새 `OCR_PENDING` 결과를 생성한다.

- `USER`는 로그인, 내 정보 조회, 활성 카테고리 조회, 영수증 제출, 본인 영수증 목록·상세·이력 조회, 반려 건 재제출을 수행한다.
- `ADMIN`은 OCR 재요청·수정, 관리자 목록 조회, 승인, 반려, 정산, 중복 후보 조회, 대시보드 조회를 수행한다.
- 영수증 소유자 또는 `ADMIN`만 영수증 상세와 처리 이력을 조회할 수 있다.
- 상태 변경은 반드시 `receipt_histories`에 기록한다.
- `SETTLED` 이후 일반 수정은 거부한다.

## 3. 전체 API 목록

| ID | Method | Endpoint | 기능 | 권한 | 요청 |
|---|---|---|---|---|---|
| `AUTH-001` | POST | `/api/auth/login` | 로그인 | 공통 | JSON body |
| `USER-001` | GET | `/api/users/me` | 내 정보와 권한 조회 | 공통 | 없음 |
| `CAT-001` | GET | `/api/categories` | 활성 카테고리 목록 조회 | 공통 | 없음 |
| `REC-001` | POST | `/api/receipts` | 영수증 제출 및 OCR 요청 | `USER` | multipart form |
| `REC-002` | GET | `/api/receipts/my` | 내 영수증 목록 조회 | `USER` | Query |
| `REC-003` | GET | `/api/receipts/{receiptId}` | 영수증 상세 조회 | 소유자 또는 `ADMIN` | Path |
| `OCR-001` | POST | `/api/receipts/{receiptId}/ocr/retry` | OCR 재요청 | `ADMIN` | Path |
| `ADM-001` | GET | `/api/admin/receipts` | 관리자 영수증 목록 조회 | `ADMIN` | Query |
| `ADM-002` | PATCH | `/api/admin/receipts/{receiptId}/ocr` | OCR 추출값 수정 및 확정 | `ADMIN` | JSON body |
| `ADM-003` | POST | `/api/admin/receipts/{receiptId}/approve` | 영수증 승인 처리 | `ADMIN` | JSON body |
| `ADM-004` | POST | `/api/admin/receipts/{receiptId}/reject` | 영수증 반려 처리 | `ADMIN` | JSON body |
| `ADM-005` | POST | `/api/admin/receipts/{receiptId}/settle` | 정산 완료 처리 | `ADMIN` | JSON body |
| `HIS-001` | GET | `/api/receipts/{receiptId}/histories` | 영수증 처리 이력 조회 | 소유자 또는 `ADMIN` | Path |
| `DUP-001` | GET | `/api/admin/receipts/{receiptId}/duplicates` | 중복 후보 조회 | `ADMIN` | Path |
| `DSH-001` | GET | `/api/admin/dashboard/summary` | 운영 대시보드 요약 조회 | `ADMIN` | Query |

## 4. 인증·공통 조회 API

### AUTH-001 로그인

`POST /api/auth/login`

Request body:

```json
{
  "email": "member@example.com",
  "password": "password1234"
}
```

성공 `data`에는 인증에 필요한 access token과 사용자 식별·권한 정보를 포함할 수 있다. `password_hash`는 포함하지 않는다.

### USER-001 내 정보 조회

`GET /api/users/me`

Request: 없음. 인증 토큰의 사용자 정보를 반환한다.

권장 `data` 필드:

```json
{
  "id": 1,
  "name": "홍길동",
  "email": "member@example.com",
  "role": "USER"
}
```

### CAT-001 활성 카테고리 목록

`GET /api/categories`

`categories.active = TRUE`인 카테고리만 반환한다.

```json
[
  { "id": 1, "name": "식비", "description": "식사 관련 지출" }
]
```

## 5. 사용자 영수증 API

### REC-001 영수증 제출

`POST /api/receipts`

Content-Type: `multipart/form-data`

| 필드 | 타입 | 필수 | DB 매핑 |
|---|---|---:|---|
| `image` | File | 예 | `receipt_files`의 Object Storage 메타데이터 |
| `purpose` | String | 예 | `receipts.purpose` |
| `categoryId` | BIGINT | 예 | `receipts.category_id` |
| `memo` | String | 아니오 | `receipts.memo` |

처리 규칙:

1. Object Storage에 파일을 저장하고 `receipt_files`에 메타데이터를 저장한다.
2. `receipts`를 `SUBMITTED`로 생성한다.
3. `receipt_histories`에 `SUBMIT`을 기록한다.
4. `ocr_results`에 새 행을 생성하고 `status`를 `OCR_PENDING`으로 저장한다.
5. OCR 성공 시 해당 결과를 `OCR_DONE`으로 변경하고, OCR 원본값을 저장한 뒤 `receipts.status`를 `REVIEWING`으로 변경한다.
6. OCR 실패 시 해당 결과를 `OCR_FAILED`로 변경하고 `receipts.status`는 `SUBMITTED`로 유지한다.

성공 `data`는 최소한 `receiptId`, `status`, `ocrStatus`를 포함한다. 제출 직후 응답 예시는 다음과 같다.

```json
{
  "receiptId": 1,
  "status": "SUBMITTED",
  "ocrStatus": "OCR_PENDING"
}
```

### REC-002 내 영수증 목록

`GET /api/receipts/my?status=APPROVED&page=0&size=20`

| Query | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `status` | String | 아니오 | 상태 필터 |
| `page` | Integer | 아니오 | 0부터 시작하는 페이지 번호 |
| `size` | Integer | 아니오 | 페이지 크기 |

조회 조건은 항상 인증 사용자의 `receipts.submitter_id`로 제한한다.

목록 항목 권장 필드:

```json
{
  "id": 1,
  "purpose": "팀 회의 식비",
  "categoryId": 1,
  "categoryName": "식비",
  "status": "APPROVED",
  "merchantName": "정상 상호",
  "paidAt": "2026-10-05",
  "amount": 18900,
  "submittedAt": "2026-10-05T14:20:00"
}
```

### REC-003 영수증 상세

`GET /api/receipts/{receiptId}`

소유자 또는 `ADMIN`만 조회할 수 있다. 상세 `data`에는 영수증 기본 정보와 파일·OCR 결과를 포함할 수 있다.

```json
{
  "id": 1,
  "submitterId": 10,
  "categoryId": 1,
  "purpose": "팀 회의 식비",
  "status": "REVIEWING",
  "merchantName": "정상 상호",
  "paidAt": "2026-10-05",
  "amount": 18900,
  "memo": "회의 후 결제",
  "file": {
    "id": 7,
    "objectKey": "receipts/2026/10/7.jpg",
    "originalFilename": "receipt.jpg",
    "contentType": "image/jpeg",
    "fileSize": 183920
  },
  "ocrResult": {
    "id": 3,
    "status": "OCR_DONE",
    "provider": "CLOVA_OCR",
    "merchantNameRaw": "정상 상호",
    "paidAtRaw": "2026-10-05",
    "amountRaw": 18900,
    "confidence": 0.98,
    "rawPayload": {}
  }
}
```

OCR 원본 필드는 `ocr_results`에서, 관리자 확정 필드는 `receipts`에서 읽는다.

### REC-004 OCR 재요청

`POST /api/receipts/{receiptId}/ocr/retry`

`ADMIN`만 호출할 수 있다. 기존 `ocr_results`를 덮어쓰지 않고 새 `OCR_PENDING` 결과를 저장한다. OCR 성공 시 새 결과를 `OCR_DONE`으로 저장하고, 실패 시 `OCR_FAILED`로 저장한다. OCR 실패 시 영수증 상태는 `SUBMITTED`로 유지한다.

## 6. 관리자 API

### ADM-001 관리자 영수증 목록

`GET /api/admin/receipts?status=REVIEWING&categoryId=1&from=2026-10-01&to=2026-10-31`

| Query | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `status` | String | 아니오 | 영수증 상태 |
| `categoryId` | BIGINT | 아니오 | 카테고리 |
| `from` | DATE | 아니오 | 시작일. PDF 기준 `receipts.paid_at` 필터 |
| `to` | DATE | 아니오 | 종료일. PDF 기준 `receipts.paid_at` 필터 |
| `page` | Integer | 아니오 | 페이지 번호 |
| `size` | Integer | 아니오 | 페이지 크기 |

### ADM-002 OCR 추출값 수정 및 확정

`PATCH /api/admin/receipts/{receiptId}/ocr`

Request body:

```json
{
  "merchantName": "정상 상호",
  "paidAt": "2026-10-05",
  "amount": 18900,
  "reason": "원본 확인 후 금액 보정"
}
```

`merchantName`, `paidAt`, `amount`는 `receipts`에 관리자 확정값으로 저장한다. OCR 원본값은 변경하지 않는다. `reason`과 변경 전·후 값은 `receipt_histories`에 저장한다.

### ADM-003 승인

`POST /api/admin/receipts/{receiptId}/approve`

Request body:

```json
{
  "comment": "검토 완료"
}
```

허용 전이는 `REVIEWING -> APPROVED`다. `receipts.reviewed_at`을 기록하고 `APPROVE` 이력을 저장한다.

### ADM-004 반려

`POST /api/admin/receipts/{receiptId}/reject`

Request body:

```json
{
  "rejectReason": "영수증 이미지가 흐려 확인이 어렵습니다."
}
```

`rejectReason`은 필수다. `reason`으로 `receipt_histories`에 저장하고 `REVIEWING -> REJECTED` 전이를 수행한다. `receipts.reviewed_at`을 기록한다.

### ADM-005 정산 완료

`POST /api/admin/receipts/{receiptId}/settle`

Request body:

```json
{
  "settledAt": "2026-10-05T15:30:00",
  "comment": "회계 처리 완료"
}
```

허용 전이는 `APPROVED -> SETTLED`다. `settlements` 행과 `SETTLE` 이력을 같은 트랜잭션으로 저장한다.

## 7. 이력·중복·대시보드 API

### HIS-001 처리 이력 조회

`GET /api/receipts/{receiptId}/histories`

소유자 또는 `ADMIN`만 조회할 수 있다.

```json
[
  {
    "id": 12,
    "actorId": 2,
    "action": "APPROVE",
    "fromStatus": "REVIEWING",
    "toStatus": "APPROVED",
    "reason": null,
    "snapshot": {},
    "createdAt": "2026-10-05T15:00:00"
  }
]
```

### DUP-001 중복 후보 조회

`GET /api/admin/receipts/{receiptId}/duplicates`

`duplicate_candidates`와 후보 영수증 정보를 반환한다. 후보 정보는 `matchReason`, `score`, `candidateReceiptId`를 포함한다.

### DSH-001 대시보드 요약

`GET /api/admin/dashboard/summary?month=2026-10`

| Query | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `month` | `YYYY-MM` | 예 | 집계 대상 월 |

`data`는 다음 집계 결과를 제공한다.

```json
{
  "month": "2026-10",
  "totalAmount": 189000,
  "categorySummaries": [
    { "categoryId": 1, "categoryName": "식비", "amount": 120000, "count": 8 }
  ],
  "pendingCount": 3,
  "rejectedCount": 1,
  "averageReviewMinutes": 42.5
}
```

집계 기준:

- 총 지출 금액: `receipts.status IN ('APPROVED', 'SETTLED')`인 `amount` 합계.
- 카테고리별 지출: `category_id`별 금액 합계와 건수.
- 미처리 건: `receipts.status IN ('SUBMITTED', 'REVIEWING')` 상태 건수. OCR 대기·실패 건은 `ocr_results.status`를 별도로 집계한다.
- 반려 건: `REJECTED` 상태 건수 및 `receipt_histories.reason` 분석.
- 평균 검토 시간: `submitted_at`부터 승인·반려 시각(`reviewed_at`)까지의 평균.

## 8. 오류 코드

| 코드 | 의미 |
|---|---|
| `AUTH_REQUIRED` | 로그인이 필요함 |
| `FORBIDDEN_ROLE` | 권한이 없는 역할의 요청 |
| `RECEIPT_NOT_FOUND` | 영수증 제출 건을 찾을 수 없음 |
| `OCR_FAILED` | CLOVA OCR 호출 또는 분석 실패 |
| `INVALID_STATUS_TRANSITION` | 허용되지 않는 상태 변경 |
| `FILE_UPLOAD_FAILED` | Object Storage 이미지 저장 실패 |

HTTP 상태 코드와 관계없이 응답 body의 `success`와 `errorCode`를 일관되게 제공한다. 인증 실패·권한 부족·리소스 없음·상태 충돌의 HTTP 상태 코드는 백엔드 구현 규칙에서 확정한다.

## 9. DB 매핑·보안 규칙

- `receiptId` -> `receipts.id`
- `categoryId` -> `categories.id`
- `merchantName`, `paidAt`, `amount` -> 관리자가 확정한 `receipts` 컬럼
- `merchantNameRaw`, `paidAtRaw`, `amountRaw`, `rawPayload` -> `ocr_results` 원본 컬럼
- `file` -> `receipt_files` 및 Object Storage 메타데이터
- `histories` -> `receipt_histories`
- `settledAt`, `comment` -> `settlements`
- `passwordHash`/`password_hash` -> 외부 API 응답·로그에서 제외
- Object Storage의 실제 공개 URL이나 비공개 접근 URL은 파일 접근 정책에 맞춰 서버가 발급한다. `object_key`를 무단으로 공개하지 않는다.

## 10. 하네스 검증 조건

- [ ] 전체 15개 endpoint의 HTTP method와 path가 일치한다.
- [ ] 공통 응답이 성공 시 `success`, `message`, `data`, 실패 시 `errorCode`를 사용한다.
- [ ] USER와 ADMIN 권한 검사가 서버에서 수행된다.
- [ ] USER 목록 조회가 본인 `submitter_id`로 제한된다.
- [ ] 상세·이력 조회가 소유자 또는 ADMIN으로 제한된다.
- [ ] 상태 전이가 명시된 그래프 밖으로 진행되지 않는다.
- [ ] 상태 변경마다 `receipt_histories`가 생성된다.
- [ ] OCR 원본과 관리자 확정값이 분리된다.
- [ ] OCR 재요청이 기존 OCR 결과를 삭제하거나 덮어쓰지 않는다.
- [ ] 반려 사유와 승인·반려 시각이 저장된다.
- [ ] 정산 저장과 `SETTLE` 이력 저장이 원자적으로 처리된다.
- [ ] `password_hash`와 access token이 응답·일반 로그에 노출되지 않는다.
- [ ] 대시보드 집계가 DB_SPEC의 상태·시간·금액 기준과 일치한다.

## 11. 원문에서 추가 확정이 필요한 항목

- API PDF의 일부 예시 JSON은 원본 PDF 레이아웃에서 문자가 겹쳐 보인다. 본 문서는 필드명과 DB 스키마를 기준으로 복원했으며, 실제 프론트·백엔드 DTO가 확정되면 샘플 값을 최종 대조한다.
- 관리자 목록의 `from`, `to`는 현재 `receipts.paid_at` 기준으로 정의했다. 제출일 필터가 필요하면 `submitted_at` 기준 여부를 별도로 결정한다.
- 페이징 응답의 구체적인 필드명(`content`, `items`, `totalElements` 등)은 PDF에 정의되지 않았으므로 구현 시 하나로 확정하고 모든 목록 API에 통일한다.
- 로그인 성공 응답의 token 만료 정책과 refresh token 여부는 PDF에 정의되지 않았다.
