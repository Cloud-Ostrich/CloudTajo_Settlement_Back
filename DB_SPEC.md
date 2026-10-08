# 구름타 조정산소 DB Specification

> 목적: Codex 하네스가 DB 스키마, 데이터 보존 규칙, 권한 범위, 상태 전이를 일관되게 구현하고 검증하기 위한 기준 문서입니다.
>
> 원본: `구름타조정산소_DB_설계.pdf`
>
> 기준 DB: Cloud DB for MySQL

## 0. 수정사항 정리

### 회의 결정 반영

- **3.3** `receipts.status`에서 `OCR_PENDING`, `OCR_DONE` 제거
- **3.5** `ocr_results.status` 추가: `OCR_PENDING`, `OCR_DONE`, `OCR_FAILED`
- **3.5** `ocr_results`에 `raw_text`, `parsed_payload`, `parser_version`, `error_message` 추가
- **3.4, 7** 재제출 시 새 이미지만 보관하는 방식 명시

### 최종 SQL에 맞춰 기존 명세 보완

- **3.1~3.8** ‘미기재’였던 NULL 허용 여부 기입
- **3.1~3.8** VARCHAR 길이, DECIMAL 자릿수, AUTO_INCREMENT, 기본값·제약조건 명시
- **2.1, 3.4, 3.7** 영수증과 파일·정산 관계를 각각 최대 한 개로 수정
- **2.1, 3.6** 시스템 작업 시 `receipt_histories.actor_id`의 NULL 허용 명시
- **3.8** 중복 후보의 동일 방향 조합 중복 금지·자기 자신 비교 금지 제약 명시
- **3.5** 선택 OCR 결과는 영수증당 최대 한 개로 백엔드에서 관리하도록 명시

### 관련 설명 정리

- **3.6** 영수증 업무 상태와 OCR 처리 이력의 기록 방식 구분
- **5.1** 영수증 업무 상태 전이와 OCR 처리 상태 전이 분리
- **6** 상태 분리에 맞춰 미처리 건 집계 기준 수정
- **7** OCR 요청·완료·실패 처리 규칙 수정
- **8** 수정된 구조와 동작에 맞춰 검증 항목 보완
- **9** 원문을 유지하고, SQL에서 확정된 부분에만 `→ 답변:` 추가

---

## 1. 구현 원칙

- 원본 영수증 이미지는 Object Storage에 저장하고, DB에는 저장 키와 파일 메타데이터만 저장한다.
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
users 1 ── N settlements              (settlements.settled_by)
categories 1 ── N receipts            (receipts.category_id)
receipts 1 ── 0..1 receipt_files      (receipt_files.receipt_id)
receipts 1 ── N ocr_results           (ocr_results.receipt_id)
receipts 1 ── N receipt_histories     (receipt_histories.receipt_id)
receipts 1 ── 0..1 settlements        (settlements.receipt_id)
receipts 1 ── N duplicate_candidates  (duplicate_candidates.receipt_id)
receipts 1 ── N duplicate_candidates  (duplicate_candidates.candidate_receipt_id)
```

`receipt_files.receipt_id`와 `settlements.receipt_id`에는 각각 UNIQUE 제약이 있으므로 영수증 한 건에 파일 기록과 정산 기록을 각각 최대 한 개만 저장할 수 있다.

`receipt_histories.actor_id`는 시스템 작업일 경우 NULL을 허용한다.

`duplicate_candidates`는 하나의 원본 영수증(`receipt_id`)과 다른 후보 영수증(`candidate_receipt_id`)을 연결하는 자기참조 관계다.

## 3. 테이블 명세

### 3.1 `users`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK, AUTO_INCREMENT | 사용자 ID |
| `name` | VARCHAR(100) | NO | - | 사용자 이름 |
| `email` | VARCHAR(255) | NO | UNIQUE | 로그인 이메일 |
| `password_hash` | VARCHAR(255) | NO | - | 비밀번호 해시. 평문 저장 금지 |
| `role` | VARCHAR(20) | NO | DEFAULT 'USER', CHECK: `USER` 또는 `ADMIN` | 사용자 역할 |
| `created_at` | DATETIME | NO | - | 생성 시각 |
| `updated_at` | DATETIME | NO | - | 수정 시각 |

### 3.2 `categories`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK, AUTO_INCREMENT | 카테고리 ID |
| `name` | VARCHAR(50) | NO | UNIQUE | 식비, 교통비, 인쇄비, 소모품비, 기타 등 |
| `description` | VARCHAR(255) | YES | - | 카테고리 설명 |
| `active` | BOOLEAN | NO | DEFAULT TRUE | 사용 여부 |

### 3.3 `receipts`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK, AUTO_INCREMENT | 영수증 제출 ID |
| `submitter_id` | BIGINT | NO | FK -> `users.id` | 제출자 |
| `category_id` | BIGINT | NO | FK -> `categories.id` | 지출 카테고리 |
| `purpose` | VARCHAR(200) | NO | - | 사용 목적 |
| `status` | VARCHAR(30) | NO | DEFAULT 'SUBMITTED', CHECK: 허용 상태 참조 | 영수증 업무 상태 |
| `merchant_name` | VARCHAR(200) | YES | - | 관리자가 확정한 상호명 |
| `paid_at` | DATE | YES | - | 관리자가 확정한 결제일 |
| `amount` | DECIMAL(15,0) | YES | - | 관리자가 확정한 금액 |
| `memo` | TEXT | YES | - | 제출자 메모 |
| `submitted_at` | DATETIME | NO | - | 제출 시각 |
| `reviewed_at` | DATETIME | YES | - | 승인 또는 반려 처리 시각 |
| `updated_at` | DATETIME | NO | - | 최종 수정 시각 |

허용 상태:

`SUBMITTED`, `REVIEWING`, `APPROVED`, `REJECTED`, `SETTLED`

OCR 처리 상태는 `ocr_results.status`에서 별도로 관리한다.

관리자가 확정한 `merchant_name`, `paid_at`, `amount`는 `ocr_results`의 원본 OCR 필드와 혼합하지 않는다.

### 3.4 `receipt_files`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK, AUTO_INCREMENT | 파일 ID |
| `receipt_id` | BIGINT | NO | FK -> `receipts.id`, UNIQUE | 영수증 제출 ID |
| `object_key` | VARCHAR(500) | NO | - | Object Storage 저장 키 |
| `original_filename` | VARCHAR(255) | NO | - | 원본 파일명 |
| `content_type` | VARCHAR(100) | NO | - | 이미지 MIME 타입 |
| `file_size` | BIGINT | NO | - | 파일 크기 |
| `uploaded_at` | DATETIME | NO | - | 업로드 시각 |

영수증 한 건에 파일 기록을 최대 한 개만 저장한다. 재제출 시 기존 파일 기록을 새 이미지 정보로 갱신하고, Object Storage의 이전 이미지 삭제는 백엔드에서 별도 처리한다.

### 3.5 `ocr_results`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK, AUTO_INCREMENT | OCR 결과 ID |
| `receipt_id` | BIGINT | NO | FK -> `receipts.id` | 영수증 제출 ID |
| `provider` | VARCHAR(30) | NO | - | OCR 제공자. 서비스에서 `CLOVA_OCR` 사용 |
| `status` | VARCHAR(30) | NO | DEFAULT 'OCR_PENDING', CHECK: 허용 상태 참조 | OCR 처리 상태 |
| `merchant_name_raw` | VARCHAR(200) | YES | - | OCR 추출 상호명 원본 |
| `paid_at_raw` | DATE | YES | - | OCR 추출 결제일 원본 |
| `amount_raw` | DECIMAL(15,0) | YES | - | OCR 추출 금액 원본 |
| `confidence` | DECIMAL(7,6) | YES | - | 인식 신뢰도 또는 내부 점수 |
| `raw_payload` | JSON | YES | - | CLOVA OCR 원본 응답 |
| `raw_text` | LONGTEXT | YES | - | OCR이 인식한 전체 텍스트 |
| `parsed_payload` | JSON | YES | - | 추출 후보·선택 근거 등 파싱 정보 |
| `parser_version` | VARCHAR(100) | YES | - | 적용한 파싱 규칙의 버전 |
| `error_message` | TEXT | YES | - | OCR 처리 실패 이유 |
| `selected` | BOOLEAN | NO | DEFAULT FALSE | 사용할 OCR 결과인지 여부 |
| `created_at` | DATETIME | NO | - | OCR 결과 생성 시각 |

허용 상태:

`OCR_PENDING`, `OCR_DONE`, `OCR_FAILED`

처리 중이거나 실패한 경우 추출값은 NULL일 수 있다.

OCR 재요청이 발생하면 기존 결과를 덮어쓰지 않고 새 결과 이력으로 저장한다. 각 요청에 생성한 행의 상태와 결과를 처리 진행에 따라 갱신한다.

영수증 한 건에 최대 한 개의 결과만 `selected = TRUE`가 되도록 백엔드에서 처리한다. 현재 SQL에는 이를 강제하는 UNIQUE 제약이 없다.

### 3.6 `receipt_histories`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK, AUTO_INCREMENT | 이력 ID |
| `receipt_id` | BIGINT | NO | FK -> `receipts.id` | 영수증 제출 ID |
| `actor_id` | BIGINT | YES | FK -> `users.id` | 처리자. 시스템 작업이면 NULL 허용 |
| `action` | VARCHAR(30) | NO | 예시 참조 | `SUBMIT`, `OCR_DONE`, `EDIT_OCR`, `APPROVE`, `REJECT`, `SETTLE` 등 |
| `from_status` | VARCHAR(30) | YES | - | 변경 전 영수증 업무 상태 |
| `to_status` | VARCHAR(30) | YES | - | 변경 후 영수증 업무 상태 |
| `reason` | TEXT | YES | - | 반려 사유 또는 수정 사유 |
| `snapshot` | JSON | YES | - | 상태 변경 시점의 주요 값 |
| `created_at` | DATETIME | NO | - | 이력 생성 시각 |

`from_status`, `to_status`는 `receipts.status`의 업무 상태를 기록한다. OCR 처리 이력은 `action`, `reason`, `snapshot`으로 기록하며, OCR 상태값을 영수증 업무 상태로 기록하지 않는다.

### 3.7 `settlements`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK, AUTO_INCREMENT | 정산 처리 ID |
| `receipt_id` | BIGINT | NO | FK -> `receipts.id`, UNIQUE | 정산 완료된 영수증 |
| `settled_by` | BIGINT | NO | FK -> `users.id` | 정산 처리 관리자 |
| `settled_at` | DATETIME | NO | - | 정산 완료 시각 |
| `comment` | TEXT | YES | - | 정산 메모 |

영수증 한 건에 정산 기록을 최대 한 개만 저장한다.

### 3.8 `duplicate_candidates`

| 컬럼 | 타입 | NULL | 제약/기본값 | 설명 |
|---|---|---:|---|---|
| `id` | BIGINT | NO | PK, AUTO_INCREMENT | 중복 후보 ID |
| `receipt_id` | BIGINT | NO | FK -> `receipts.id` | 검사 대상 영수증 |
| `candidate_receipt_id` | BIGINT | NO | FK -> `receipts.id` | 중복 후보 영수증 |
| `match_reason` | VARCHAR(255) | NO | - | 금액, 상호명, 결제일, 제출 시각 등의 매칭 근거 |
| `score` | DECIMAL(7,6) | YES | - | 유사도 점수 |
| `created_at` | DATETIME | NO | - | 후보 생성 시각 |

- `UNIQUE(receipt_id, candidate_receipt_id)`로 동일한 방향의 영수증 ID 조합 중복 저장을 금지한다.
- `CHECK(receipt_id <> candidate_receipt_id)`로 자기 자신을 후보로 저장하는 것을 금지한다.
- 역방향 조합인 `(A, B)`와 `(B, A)`는 현재 제약조건에서 서로 다른 조합으로 취급한다.

## 4. 인덱스

| 테이블 | 인덱스/제약 | 목적 |
|---|---|---|
| `users` | `UNIQUE(email)` | 로그인 및 중복 가입 방지 |
| `receipts` | (`submitter_id`, `status`, `category_id`, `paid_at`) | 본인 제출 현황, 관리자 필터, 기간·카테고리 조회 |
| `receipts` | (`merchant_name`, `amount`, `paid_at`) | 중복 영수증 또는 유사 지출 후보 탐지 |
| `ocr_results` | (`receipt_id`, `created_at`) | OCR 재요청 이력 조회 |
| `receipt_histories` | (`receipt_id`, `actor_id`, `created_at`) | 처리 이력 및 감사 로그 조회 |
| `settlements` | (`receipt_id`, `settled_at`) | 정산 완료 내역 및 월별 집계 |

실제 인덱스 생성 시 조회 쿼리의 선두 조건과 데이터 분포를 확인한다. 위 목록은 PDF의 인덱스 초안이며, 인덱스 이름은 구현 시 정한다.

## 5. 상태 전이 및 권한

### 5.1 허용 전이

영수증 업무 상태(`receipts.status`):

```text
SUBMITTED -> REVIEWING
REVIEWING -> APPROVED -> SETTLED
REVIEWING -> REJECTED -> SUBMITTED   (사용자 재제출)
```

OCR 처리 상태(`ocr_results.status`):

```text
OCR_PENDING -> OCR_DONE
OCR_PENDING -> OCR_FAILED
```

OCR 재요청 시 새 `ocr_results` 행을 `OCR_PENDING` 상태로 생성하고 기존 요청 결과는 보존한다. OCR 처리 상태 변경만으로 `receipts.status`를 변경하지 않는다.

- `USER`: 제출, 본인 목록 조회, 반려 건 재제출만 수행한다.
- `ADMIN`: OCR 결과 수정, 승인, 반려, 정산 완료, 대시보드 조회를 수행한다.
- 영수증 업무 상태가 바뀔 때마다 `receipt_histories`에 처리자, action, 이전 상태, 이후 상태, 사유, 시각을 저장한다.
- OCR 처리 상태 변경도 `receipt_histories`에 기록하며, OCR 상태와 결과는 `action`, `reason`, `snapshot`으로 남긴다.
- `SETTLED` 이후 수정은 기본적으로 거부한다.
- 사용자는 다른 사용자의 영수증, 파일, OCR 결과, 이력, 정산 정보를 조회할 수 없다.
- 관리자는 관리자 기능에 필요한 범위에서 전체 영수증을 조회할 수 있다.

## 6. 대시보드 집계 기준

- 월별 총 지출 금액: `receipts.status IN ('APPROVED', 'SETTLED')`인 행의 `amount` 합계.
- 카테고리별 지출: `category_id`별 금액 합계와 건수.
- 미처리 건: `receipts.status IN ('SUBMITTED', 'REVIEWING')`인 영수증 건수. OCR 처리 상태와 별개로 영수증 기준으로 집계한다.
- 반려 건: `REJECTED` 상태 건수와 `receipt_histories.reason` 기반 사유 분석.
- 평균 검토 시간: 제출 시각부터 승인 또는 반려 시각까지의 평균. 구현 시 `submitted_at`과 `reviewed_at`을 사용한다.

## 7. 트랜잭션 규칙

### 제출

1. `receipts`를 `SUBMITTED` 상태로 생성한다.
2. `receipt_files`에 Object Storage 파일 메타데이터를 저장한다.
3. `receipt_histories`에 `SUBMIT` 이력을 저장한다.
4. OCR 요청을 시작할 경우 새 `ocr_results` 행을 `OCR_PENDING` 상태로 생성하고 이력을 추가한다. `receipts.status`는 OCR 요청 때문에 변경하지 않는다.

파일 저장과 DB 저장 중 하나라도 실패하면 제출을 성공으로 응답하지 않는다. Object Storage에 먼저 저장된 파일이 DB 저장 실패로 고아 파일이 되지 않도록 보상 삭제 또는 정리 작업을 둔다.

### OCR 완료 및 관리자 검토

1. OCR 요청 시 생성한 `ocr_results` 행에 OCR 원본 응답과 추출값, 파싱 정보를 저장한다.
2. 이전 OCR 요청의 결과는 덮어쓰지 않는다. 재요청은 새 행으로 생성한다.
3. OCR 성공 시 해당 행의 `status`를 `OCR_DONE`으로 변경하고 이력을 저장한다. 실패 시 `OCR_FAILED`로 변경하고 `error_message` 및 이력을 저장한다. OCR 처리 결과만으로 `receipts.status`를 변경하지 않는다.
4. 관리자가 검토를 시작하면 `receipts.status`를 `REVIEWING`으로 변경하고 이력을 저장한다.
5. 관리자가 확정한 값을 `receipts.merchant_name`, `paid_at`, `amount`에 저장한다.

### 승인, 반려, 정산

- 승인: `REVIEWING -> APPROVED`, `reviewed_at` 기록, `APPROVE` 이력 저장.
- 반려: `REVIEWING -> REJECTED`, `reviewed_at` 기록, `reason` 필수, `REJECT` 이력 저장.
- 재제출: `REJECTED -> SUBMITTED`, 기존 반려 이력을 보존하고 새 `SUBMIT` 이력 저장. 기존 `receipt_files` 행을 새 이미지 정보로 갱신하며, Object Storage의 이전 이미지는 백엔드에서 별도 삭제한다.
- 정산: `APPROVED -> SETTLED`, `settlements`와 `SETTLE` 이력을 같은 트랜잭션으로 저장한다.

## 8. 하네스 검증 조건

Codex가 구현을 완료했다고 판단하려면 다음 조건을 모두 만족해야 한다.

- [ ] 8개 테이블이 모두 존재한다.
- [ ] 각 테이블의 PK, FK, 타입, NULL 여부, 기본값, UNIQUE 및 CHECK 제약이 이 문서와 일치한다.
- [ ] `password_hash`가 API 응답이나 로그에 노출되지 않는다.
- [ ] OCR 원본값과 관리자 확정값이 서로 다른 컬럼에 저장된다.
- [ ] 영수증 업무 상태와 OCR 처리 상태가 각각 `receipts.status`, `ocr_results.status`에서 별도로 관리된다.
- [ ] `receipt_histories` 없이 영수증 업무 상태나 OCR 처리 상태가 변경되지 않는다.
- [ ] 사용자는 본인 영수증만 조회하고, 관리자는 관리자 범위의 영수증을 조회한다.
- [ ] `SETTLED` 상태의 일반 수정 요청이 거부된다.
- [ ] 승인·반려 시 `reviewed_at`이 기록된다.
- [ ] 정산 완료 시 `settlements.settled_at`과 `settlements.settled_by`가 저장된다.
- [ ] 반려 시 `receipt_histories.reason`이 저장된다.
- [ ] OCR 재요청 시 기존 `ocr_results`가 보존된다.
- [ ] OCR 실패 시 `ocr_results.status`에 `OCR_FAILED`가 저장되고 실패 이유가 `error_message`에 기록된다.
- [ ] 영수증별 `selected = TRUE`인 OCR 결과가 최대 한 개로 유지된다.
- [ ] 재제출 시 파일 기록은 최대 한 개로 유지되고 새 이미지 정보로 갱신된다.
- [ ] PDF에 정의된 인덱스 목적을 만족하는 조회가 동작한다.
- [ ] 대시보드 집계가 위 기준 상태와 컬럼을 사용한다.

## 9. 원문과 구현 사이의 확인 항목

다음 항목은 PDF에 구조가 표시되어 있으나 실제 DDL에서 최종 확인해야 한다.

- PDF ERD에는 `created_at`, `updated_at`, `submitted_at`, `reviewed_at`, `uploaded_at`, `selected`가 표시되지만 일부 상세 표에는 생략되어 있다. 본 명세는 ERD에 표시된 컬럼을 기준으로 포함했다.
  → 답변: 최종 schema.sql에 해당 컬럼을 모두 포함했습니다. `reviewed_at`은 NULL을 허용하고, 나머지 컬럼은 NOT NULL로 지정했습니다. `selected`의 기본값은 FALSE입니다.

- PDF는 날짜/시각 컬럼의 정밀도와 타임존을 지정하지 않았다. 애플리케이션과 DB의 타임존 정책을 구현 전에 확정한다.

- PDF는 `settlements.receipt_id`와 `ocr_results.selected`의 UNIQUE 여부를 지정하지 않았다. 중복 정산 방지와 선택 OCR 결과의 단일성은 서비스 정책 확정 후 별도 제약으로 결정한다.
  → 답변: 최종 schema.sql에서 `settlements.receipt_id`에 UNIQUE 제약을 적용하여 영수증당 정산 기록을 최대 한 개로 제한했습니다. `ocr_results.selected`에는 UNIQUE 제약을 적용하지 않았으며, 영수증당 최대 한 개만 TRUE로 선택하는 규칙은 백엔드에서 처리하도록 SQL 주석에 명시했습니다.

- PDF의 ERD 링크는 `erdcloude 링크`로만 표시되어 있어 외부 ERD 링크를 이 문서에 임의로 만들지 않았다.
