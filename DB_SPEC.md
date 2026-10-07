# 구름타 조정산소 DB Specification

> 목적: Codex 하네스가 DB 스키마, 데이터 보존 규칙, 권한 범위, 상태 전이를 일관되게 구현하고 검증하기 위한 기준 문서입니다.
>
> 원본: `구름타조정산소_DB_설계.pdf`
>
> 기준 DB: Cloud DB for MySQL

## 1. 구현 원칙

- 원본 영수증 이미지는 Object Storage에 비공개로 저장하고, DB에는 저장 키와 파일 메타데이터만 저장한다. 저장 키 prefix는 `receipts/{year}/{month}/`를 사용하며, 파일 제공 전 API에서 영수증 소유자 또는 `ADMIN`인지 확인한다.
- OCR 결과는 자동 확정하지 않는다. OCR 원본값은 `ocr_results`에 보존하고, 관리자가 확정한 값은 `receipts`에 저장한다.
- 상태 변경, OCR 수정, 승인, 반려, 정산은 반드시 `receipt_histories`에 기록한다.
- 사용자(`USER`)와 관리자(`ADMIN`) 권한은 화면뿐 아니라 API 서버의 조회 범위와 DB 조회 조건에도 적용한다.
- 중복 후보 탐지를 위해 상호명, 결제일, 금액, 제출 시각을 조회할 수 있어야 한다.
- `SETTLED` 상태 이후 영수증 수정은 원칙적으로 제한한다. 예외가 필요하면 관리자 이력으로 남긴다.
- 아래 명세의 `NULL`은 값이 없을 수 있음을 뜻하며, 빈 문자열로 대체하지 않는다.

## 2. 데이터 모델

### 2.1 관계

```text
users 1 ── N receipts                 (receipts.submitter_id)
users 1 ── N receipt_histories         (receipt_histories.actor_id)
users 1 ── N settlements                (settlements.settled_by)
categories 1 ── N receipts             (receipts.category_id)
receipts 1 ── N receipt_files          (receipt_files.receipt_id)
receipts 1 ── N ocr_results            (ocr_results.receipt_id)
receipts 1 ── N receipt_histories      (receipt_histories.receipt_id)
receipts 1 ── N settlements             (settlements.receipt_id)
receipts 1 ── N duplicate_candidates   (duplicate_candidates.receipt_id)
receipts 1 ── N duplicate_candidates   (duplicate_candidates.candidate_receipt_id)
```

`duplicate_candidates`는 하나의 원본 영수증(`receipt_id`)과 다른 후보 영수증(`candidate_receipt_id`)을 연결하는 자기참조 관계다.

## 3. 테이블 명세

### 3.1 `users`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK | 사용자 ID |
| `name` | VARCHAR | NO | - | 사용자 이름 |
| `email` | VARCHAR | NO | UNIQUE | 로그인 이메일 |
| `password_hash` | VARCHAR | NO | - | 암호화된 비밀번호. 평문 저장 금지 |
| `role` | VARCHAR | NO | `USER` 또는 `ADMIN` | 사용자 역할 |
| `created_at` | DATETIME | 미기재 | - | 생성 시각 |
| `updated_at` | DATETIME | 미기재 | - | 수정 시각 |

### 3.2 `categories`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK | 카테고리 ID |
| `name` | VARCHAR | NO | UNIQUE | 식비, 교통비, 인쇄비, 소모품비, 기타 등 |
| `description` | VARCHAR | YES | - | 카테고리 설명 |
| `active` | BOOLEAN | NO | DEFAULT TRUE | 사용 여부 |

### 3.3 `receipts`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK | 영수증 제출 ID |
| `submitter_id` | BIGINT | 미기재 | FK -> `users.id` | 제출자 |
| `category_id` | BIGINT | 미기재 | FK -> `categories.id` | 지출 카테고리 |
| `purpose` | VARCHAR | NO | - | 사용 목적 |
| `status` | VARCHAR | NO | 허용 상태 참조 | 영수증 처리 상태 |
| `merchant_name` | VARCHAR | YES | - | 관리자가 확정한 상호명 |
| `paid_at` | DATE | YES | - | 관리자가 확정한 결제일 |
| `amount` | DECIMAL | YES | - | 관리자가 확정한 금액 |
| `memo` | TEXT | YES | - | 제출자 메모 |
| `submitted_at` | DATETIME | 미기재 | - | 제출 시각 |
| `reviewed_at` | DATETIME | 미기재 | - | 승인 또는 반려 처리 시각 |
| `updated_at` | DATETIME | 미기재 | - | 최종 수정 시각 |

허용 상태:

`SUBMITTED`, `REVIEWING`, `APPROVED`, `REJECTED`, `SETTLED`

관리자가 확정한 `merchant_name`, `paid_at`, `amount`는 `ocr_results`의 원본 OCR 필드와 혼합하지 않는다.

### 3.4 `receipt_files`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK | 파일 ID |
| `receipt_id` | BIGINT | 미기재 | FK -> `receipts.id` | 영수증 제출 ID |
| `object_key` | VARCHAR | NO | - | Object Storage 저장 키 |
| `original_filename` | VARCHAR | NO | - | 원본 파일명 |
| `content_type` | VARCHAR | NO | - | 이미지 MIME 타입 |
| `file_size` | BIGINT | NO | - | 파일 크기 |
| `uploaded_at` | DATETIME | 미기재 | - | 업로드 시각 |

### 3.5 `ocr_results`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK | OCR 결과 ID |
| `receipt_id` | BIGINT | 미기재 | FK -> `receipts.id` | 영수증 제출 ID |
| `status` | VARCHAR | NO | `OCR_PENDING`, `OCR_DONE`, `OCR_FAILED` | OCR 처리 상태 |
| `provider` | VARCHAR | NO | `CLOVA_OCR` | OCR 제공자 |
| `merchant_name_raw` | VARCHAR | YES | - | OCR 추출 상호명 원본 |
| `paid_at_raw` | DATE | YES | - | OCR 추출 결제일 원본 |
| `amount_raw` | DECIMAL | YES | - | OCR 추출 금액 원본 |
| `confidence` | DECIMAL | YES | - | 인식 신뢰도 또는 내부 점수 |
| `raw_payload` | JSON | YES | - | CLOVA OCR 원본 응답 |
| `selected` | BOOLEAN | 미기재 | - | 사용할 OCR 결과인지 여부 |
| `created_at` | DATETIME | 미기재 | - | OCR 결과 생성 시각 |

OCR 재요청이 발생하면 기존 결과를 덮어쓰지 않고 새 결과 행을 `OCR_PENDING` 상태로 저장한다. 처리 성공 시 `OCR_DONE`, 실패 시 `OCR_FAILED`로 변경한다.

### 3.6 `receipt_histories`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK | 이력 ID |
| `receipt_id` | BIGINT | 미기재 | FK -> `receipts.id` | 영수증 제출 ID |
| `actor_id` | BIGINT | 미기재 | FK -> `users.id` | 처리자 |
| `action` | VARCHAR | NO | 예시 참조 | `SUBMIT`, `OCR_DONE`, `EDIT_OCR`, `APPROVE`, `REJECT`, `SETTLE` 등 |
| `from_status` | VARCHAR | YES | - | 변경 전 상태 |
| `to_status` | VARCHAR | YES | - | 변경 후 상태 |
| `reason` | TEXT | YES | - | 반려 사유 또는 수정 사유 |
| `snapshot` | JSON | YES | - | 상태 변경 시점의 주요 값 |
| `created_at` | DATETIME | 미기재 | - | 이력 생성 시각 |

### 3.7 `settlements`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK | 정산 처리 ID |
| `receipt_id` | BIGINT | 미기재 | FK -> `receipts.id` | 정산 완료된 영수증 |
| `settled_by` | BIGINT | 미기재 | FK -> `users.id` | 정산 처리 관리자 |
| `settled_at` | DATETIME | NO | - | 정산 완료 시각 |
| `comment` | TEXT | YES | - | 정산 메모 |

### 3.8 `duplicate_candidates`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK | 중복 후보 ID |
| `receipt_id` | BIGINT | 미기재 | FK -> `receipts.id` | 검사 대상 영수증 |
| `candidate_receipt_id` | BIGINT | 미기재 | FK -> `receipts.id` | 중복 후보 영수증 |
| `match_reason` | VARCHAR | NO | - | 금액, 상호명, 결제일, 제출 시각 등의 매칭 근거 |
| `score` | DECIMAL | YES | - | 유사도 점수 |
| `created_at` | DATETIME | 미기재 | - | 후보 생성 시각 |

## 4. 인덱스

| 테이블 | 인덱스/제약 | 목적 |
|---|---|---|
| `users` | `UNIQUE(email)` | 로그인 및 중복 가입 방지 |
| `receipts` | (`submitter_id`, `status`, `category_id`, `paid_at`) | 본인 제출 현황, 관리자 필터, 기간·카테고리 조회 |
| `receipts` | (`merchant_name`, `amount`, `paid_at`) | 중복 영수증 또는 유사 지출 후보 탐지 |
| `ocr_results` | (`receipt_id`, `status`, `created_at`) | OCR 상태 및 재요청 이력 조회 |
| `receipt_histories` | (`receipt_id`, `actor_id`, `created_at`) | 처리 이력 및 감사 로그 조회 |
| `settlements` | (`receipt_id`, `settled_at`) | 정산 완료 내역 및 월별 집계 |

실제 인덱스 생성 시 조회 쿼리의 선두 조건과 데이터 분포를 확인한다. 위 목록은 PDF의 인덱스 초안이며, 인덱스 이름은 구현 시 정한다.

## 5. 상태 전이 및 권한

### 5.1 허용 전이

```text
SUBMITTED -> REVIEWING
REVIEWING -> APPROVED -> SETTLED
REVIEWING -> REJECTED -> SUBMITTED   (사용자 재제출)
```

OCR 상태 전이:

```text
OCR_PENDING -> OCR_DONE
            -> OCR_FAILED
```

- `USER`: 제출, 본인 목록 조회, 반려 건 재제출만 수행한다.
- `ADMIN`: OCR 결과 수정, 승인, 반려, 정산 완료, 대시보드 조회를 수행한다.
- 상태가 바뀔 때마다 `receipt_histories`에 처리자, action, 이전 상태, 이후 상태, 사유, 시각을 저장한다.
- `SETTLED` 이후 수정은 기본적으로 거부한다.
- 사용자는 다른 사용자의 영수증, 파일, OCR 결과, 이력, 정산 정보를 조회할 수 없다.
- 관리자는 관리자 기능에 필요한 범위에서 전체 영수증을 조회할 수 있다.

## 6. 대시보드 집계 기준

- 월별 총 지출 금액: `receipts.status IN ('APPROVED', 'SETTLED')`인 행의 `amount` 합계.
- 카테고리별 지출: `category_id`별 금액 합계와 건수.
- 미처리 건: `receipts.status IN ('SUBMITTED', 'REVIEWING')` 상태 건수. OCR 대기·실패 건은 `ocr_results.status`를 별도로 집계한다.
- 반려 건: `REJECTED` 상태 건수와 `receipt_histories.reason` 기반 사유 분석.
- 평균 검토 시간: 제출 시각부터 승인 또는 반려 시각까지의 평균. 구현 시 `submitted_at`과 `reviewed_at`을 사용한다.

## 7. 트랜잭션 규칙

### 제출

1. `receipts`를 `SUBMITTED` 상태로 생성한다.
2. `receipt_files`에 Object Storage 파일 메타데이터를 저장한다.
3. `receipt_histories`에 `SUBMIT` 이력을 저장한다.
4. `ocr_results`에 `OCR_PENDING` 상태의 새 행을 저장하고 `OCR_PENDING` 이력을 추가한다.
5. OCR 성공 시 같은 결과 행을 `OCR_DONE`으로 변경하고 OCR 원본값을 저장한다.
6. OCR 완료 후 `receipts.status`를 `REVIEWING`으로 변경하고 이력을 저장한다.
7. OCR 실패 시 결과 행을 `OCR_FAILED`로 변경하고 이력을 저장한다. 이때 `receipts.status`는 `SUBMITTED`로 유지한다.

파일 저장과 DB 저장 중 하나라도 실패하면 제출을 성공으로 응답하지 않는다. Object Storage에 먼저 저장된 파일이 DB 저장 실패로 고아 파일이 되지 않도록 보상 삭제 또는 정리 작업을 둔다.

### OCR 완료 및 관리자 검토

1. OCR 원본 응답을 새 `ocr_results` 행에 저장한다.
2. 기존 OCR 결과를 덮어쓰지 않는다.
3. 성공한 결과의 `ocr_results.status`를 `OCR_DONE`으로 변경하고 이력을 저장한다.
4. OCR 완료 후 `receipts.status`를 `REVIEWING`으로 변경한다.
5. 관리자가 확정한 값을 `receipts.merchant_name`, `paid_at`, `amount`에 저장한다.

OCR 실패 시 `ocr_results.status`를 `OCR_FAILED`로 변경하고, `receipts.status`는 `SUBMITTED`로 유지한다. 재요청 시 기존 OCR 결과를 보존한 채 새 `OCR_PENDING` 행을 생성한다.

### 승인, 반려, 정산

- 승인: `REVIEWING -> APPROVED`, `reviewed_at` 기록, `APPROVE` 이력 저장.
- 반려: `REVIEWING -> REJECTED`, `reviewed_at` 기록, `reason` 필수, `REJECT` 이력 저장.
- 재제출: `REJECTED -> SUBMITTED`, 기존 반려 이력을 보존하고 새 `SUBMIT` 이력 저장.
- 정산: `APPROVED -> SETTLED`, `settlements`와 `SETTLE` 이력을 같은 트랜잭션으로 저장한다.

## 8. 하네스 검증 조건

Codex가 구현을 완료했다고 판단하려면 다음 조건을 모두 만족해야 한다.

- [ ] 8개 테이블이 모두 존재한다.
- [ ] 각 테이블의 PK, FK, 타입, NULL 여부가 이 문서와 일치한다.
- [ ] `password_hash`가 API 응답이나 로그에 노출되지 않는다.
- [ ] OCR 원본값과 관리자 확정값이 서로 다른 컬럼에 저장된다.
- [ ] `receipt_histories` 없이 상태가 변경되지 않는다.
- [ ] 사용자는 본인 영수증만 조회하고, 관리자는 관리자 범위의 영수증을 조회한다.
- [ ] `SETTLED` 상태의 일반 수정 요청이 거부된다.
- [ ] 승인·반려 시 `reviewed_at`이 기록된다.
- [ ] 정산 완료 시 `settlements.settled_at`과 `settlements.settled_by`가 저장된다.
- [ ] 반려 시 `receipt_histories.reason`이 저장된다.
- [ ] OCR 상태가 `ocr_results.status`에 `OCR_PENDING`, `OCR_DONE`, `OCR_FAILED`로 저장된다.
- [ ] OCR 재요청 시 기존 `ocr_results`가 보존된다.
- [ ] PDF에 정의된 인덱스 목적을 만족하는 조회가 동작한다.
- [ ] 대시보드 집계가 위 기준 상태와 컬럼을 사용한다.

## 9. 원문과 구현 사이의 확인 항목

다음 항목은 PDF에 구조가 표시되어 있으나 실제 DDL에서 최종 확인해야 한다.

- PDF ERD에는 `created_at`, `updated_at`, `submitted_at`, `reviewed_at`, `uploaded_at`, `selected`가 표시되지만 일부 상세 표에는 생략되어 있다. 본 명세는 ERD에 표시된 컬럼을 기준으로 포함했다.
- PDF는 날짜/시각 컬럼의 정밀도와 타임존을 지정하지 않았다. 애플리케이션과 DB의 타임존 정책을 구현 전에 확정한다.
- PDF는 `settlements.receipt_id`와 `ocr_results.selected`의 UNIQUE 여부를 지정하지 않았다. 중복 정산 방지와 선택 OCR 결과의 단일성은 서비스 정책 확정 후 별도 제약으로 결정한다.
- PDF의 ERD 링크는 `erdcloude 링크`로만 표시되어 있어 외부 ERD 링크를 이 문서에 임의로 만들지 않았다.
