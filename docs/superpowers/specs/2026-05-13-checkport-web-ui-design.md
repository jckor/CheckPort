# CheckPort Web UI — Design Spec

**Date:** 2026-05-13  
**Scope:** Flask 기반 선박 입출항 조회 웹 앱 신규 개발  
**Status:** Approved

---

## 1. 목표

`CheckPort.py`의 하드코딩 방식 실행을 대체하여, 사내 서버에 배포 가능한 웹 UI를 제공한다.  
사용자가 브라우저에서 항만청코드·조회 기간을 입력하면 결과를 페이징 테이블로 확인하고, XLSX로 다운로드할 수 있다.

---

## 2. 환경 및 기술 스택

| 항목 | 선택 |
|---|---|
| 배포 환경 | 사내 서버 |
| 언어 | Python 3.13 |
| 웹 프레임워크 | Flask |
| 템플릿 | Jinja2 (Flask 내장) |
| 날짜 선택기 | HTML5 `<input type="date">` |
| XLSX 생성 | openpyxl |
| 클라이언트 페이징/필터 | Vanilla JS |
| API 키 관리 | `SERVICE_KEY` 환경변수 — UI에 미노출 |

---

## 3. 파일 구조

```
~/Code/
  app.py                        # Flask 앱 진입점 (신규)
  templates/
    index.html                  # 조회 폼 + 결과 테이블 (신규)
  fetch_vessel_movements_daily.py   # 기존 — 수정 없음
  CheckPort.py                  # 기존 유지 (CLI 방식도 유지)
```

---

## 4. 아키텍처 및 데이터 흐름

### 조회

```
[브라우저] POST /query  {prtAgCd, start_date, end_date}
    ↓
[Flask app.py]
  → SERVICE_KEY 환경변수 읽기
  → fetch_vessel_movements_daily() 내부 로직 재사용
     (CSV 저장 없이 all_details 리스트만 반환하도록 리팩토링)
  → JSON 응답: { records: [...], total: N }
    ↓
[브라우저 JS]
  → Summary 카드 계산 및 렌더링
  → vessel_type / cargo_type_name 드롭다운 자동 생성
  → 테이블 100개씩 페이징 렌더링
```

### XLSX 다운로드

```
[브라우저] GET /export?prtAgCd=621&start_date=20250801&end_date=20250831
    ↓
[Flask app.py]
  → API 재호출 (또는 세션 미사용 — 파라미터 기반 재생성)
  → openpyxl로 .xlsx 생성
     시트1: Summary  /  시트2: 상세 데이터
  → Content-Disposition: attachment 파일 응답
     파일명: vessel_movements_{prtAgCd}_{start}_{end}.xlsx
```

---

## 5. Flask 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 조회 폼 페이지 반환 |
| POST | `/query` | API 호출 → JSON 반환 |
| GET | `/export` | XLSX 파일 생성 및 다운로드 |

---

## 6. UI 레이아웃

```
┌─────────────────────────────────────────────────────────────┐
│  선박 입출항 조회 시스템                                      │
├─────────────────────────────────────────────────────────────┤
│  항만청코드: [드롭다운 ▼] 또는 [직접 입력 _____]             │
│  조회 시작일: [날짜 선택기]  종료일: [날짜 선택기]            │
│                              [조회하기]                       │
├─────────────────────────────────────────────────────────────┤
│  ── Summary ──────────────────────────────────────────────  │
│  총 레코드 | 입항 | 출항 | 선박 종류 수 | 선적/양하/환적 톤  │
├─────────────────────────────────────────────────────────────┤
│  필터: [선박명 검색] [선박종류 ▼] [화물종류 ▼] [초기화]      │
│                              [XLSX 다운로드]                  │
├─────────────────────────────────────────────────────────────┤
│  테이블 (100개씩 페이징)                                      │
│  날짜 | 입출항 | 항만 | 선박명 | 종류 | 국적 | 화물 | 톤수…  │
│  « 이전  [1][2][3]… 다음 »   총 N건 / M페이지               │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Summary 카드 항목

| 카드 | 계산 방법 |
|---|---|
| 총 레코드 수 | `records.length` |
| 입항 건수 | `entry_exit === '입항'` count |
| 출항 건수 | `entry_exit === '출항'` count |
| 선박 종류 수 | 고유 `vessel_type` 개수 |
| 선적 화물 합계 (톤) | `ld_ton` 합계 |
| 양하 화물 합계 (톤) | `landng_ton` 합계 |
| 환적 화물 합계 (톤) | `trnpdt_ton` 합계 |

---

## 8. XLSX 구성

- **시트 1 — Summary**: 위 7개 통계 항목
- **시트 2 — 상세 데이터**: 전체 레코드 (클라이언트 필터 무관)
- **파일명**: `vessel_movements_{prtAgCd}_{start_date}_{end_date}.xlsx`

---

## 9. 클라이언트 필터 (Vanilla JS)

- **선박명 검색**: `vessel_name`에 대한 substring 대소문자 무시 검색
- **선박종류 드롭다운**: 조회 결과의 고유 `vessel_type` 값으로 자동 구성
- **화물종류 드롭다운**: 조회 결과의 고유 `cargo_type_name` 값으로 자동 구성
- 필터 변경 시 페이지를 1로 초기화하고 테이블 재렌더링

---

## 10. 주요 항만청코드 (드롭다운 기본값)

| 코드 | 항만명 |
|---|---|
| 621 | 여수항 |
| 011 | 부산항 |
| 021 | 인천항 |
| 031 | 울산항 |
| 041 | 광양항 |
| 051 | 마산항 |
| 061 | 목포항 |

---

## 11. 기존 코드 재활용 전략

`fetch_vessel_movements_daily.py`에서 API 호출 + XML 파싱 로직만 담당하는 `fetch_vessel_records()` 함수를 **신규 추출**한다.
- `fetch_vessel_records(service_key, prtAgCd, start_date, end_date)` → `list[dict]` 반환 (CSV 저장 없음)
- 기존 `fetch_vessel_movements_daily()`는 내부에서 `fetch_vessel_records()`를 호출하고 CSV 저장을 추가 수행 — 기존 CLI 방식(`CheckPort.py`) 호환성 보존.
- Flask `app.py`와 `/export` 엔드포인트 모두 `fetch_vessel_records()`를 사용.

---

## 12. 의존성 추가

```
flask
openpyxl
```

기존 의존성 (`requests`, `pandas`, `numpy`, `folium`)은 변경 없음.
