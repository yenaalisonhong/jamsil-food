# API 설정 가이드 — 프라운호퍼 잠실 맛집 탐방

프라운호퍼 한국사무소(잠실더샵스타파크) 기준으로 주변 맛집/카페를 검색하고, 신규 오픈 알림을 받기 위한 API·알림 설정 방법입니다.

---

## 1. 사무실 기준 위치

| 항목 | 값 |
|------|-----|
| **주소** | 서울시 송파구 올림픽로 35가길 10, A동 202호 (신천동, 잠실더샵스타파크) |
| **우편번호** | 05510 |
| **기본 좌표** | 위도 `37.51692`, 경도 `127.10282` |
| **검색 반경** | 도보 15분 ≈ **1,200m** (설정: `MAX_WALK_MINUTES=15`) |

좌표는 `config/settings.py`의 `fraunhofer_office_lat`, `fraunhofer_office_lng`에서 관리합니다.  
`.env`로 덮어쓸 수 있습니다:

```env
FRAUNHOFER_OFFICE_LAT=37.51692
FRAUNHOFER_OFFICE_LNG=127.10282
```

### 좌표 직접 확인 (Kakao 주소 검색 API)

발급받은 REST API 키로 사무실 주소의 좌표를 검증할 수 있습니다.

```powershell
# PowerShell
$KEY = "여기에_REST_API_키"
$QUERY = "서울시 송파구 올림픽로 35가길 10 잠실더샵스타파크"
curl.exe -G "https://dapi.kakao.com/v2/local/search/address.json" `
  -H "Authorization: KakaoAK $KEY" `
  --data-urlencode "query=$QUERY"
```

응답 `documents[0].y`(위도), `documents[0].x`(경도)를 `.env`에 반영하세요.

---

## 2. Kakao REST API (이미 발급 완료)

### 2-1. 키 종류 확인

| 키 종류 | 용도 | 이 프로젝트 |
|---------|------|-------------|
| **REST API 키** | 서버에서 Local API 호출 | ✅ **필수** — 맛집/카페 검색 |
| JavaScript 키 | 웹 지도 SDK | 웹앱 만들 때만 필요 |
| Admin 키 | 사용자 관리 등 | 불필요 |

> ⚠️ **REST API 키 ≠ 카카오톡 알림 API**  
> 지금 발급받은 키로는 **장소 검색만** 가능합니다. 카카오톡 자동 발송은 별도 비즈니스 연동이 필요합니다 (3장 참고).

### 2-2. 카카오 개발자 콘솔 설정

1. [Kakao Developers](https://developers.kakao.com/) → 내 애플리케이션 선택
2. **앱 설정 → 앱 키**에서 **REST API 키** 복사
3. **제품 설정 → 카카오맵** → **활성화 ON** (Local API 사용 조건)
4. (선택) **플랫폼**에 서버 IP 또는 `localhost` 등록

### 2-3. `.env` 설정

프로젝트 루트에 `.env` 파일 생성 (`.env.example` 복사):

```powershell
Copy-Item .env.example .env
```

```env
KAKAO_REST_API_KEY=발급받은_REST_API_키
```

### 2-4. 이 프로젝트에서 쓰는 Kakao API

| API | 엔드포인트 | 용도 |
|-----|-----------|------|
| 키워드로 장소 검색 | `GET /v2/local/search/keyword.json` | 음식점(FD6), 카페(CE7) 검색 |
| 주소로 좌표 변환 | `GET /v2/local/search/address.json` | 사무실 좌표 검증 |

**호출 예시 (음식점 검색):**

```powershell
curl.exe -G "https://dapi.kakao.com/v2/local/search/keyword.json" `
  -H "Authorization: KakaoAK $KEY" `
  --data-urlencode "query=음식점" `
  --data-urlencode "x=127.10282" `
  --data-urlencode "y=37.51692" `
  --data-urlencode "radius=1200" `
  --data-urlencode "category_group_code=FD6"
```

**일일 호출 한도:** 무료 약 30만 건/일 (앱별 상이, [콘솔](https://developers.kakao.com/)에서 확인)

**공식 문서:** [Kakao Local API](https://developers.kakao.com/docs/latest/ko/local/dev-guide)

### 2-5. Kakao API 한계 (알아두기)

- **평점 미제공** → Naver API 등으로 보완 예정 (`NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET`)
- **개업일 미제공** → 신규 오픈 알림(기능 C)은 Mock 데이터 또는 Naver 등 추가 연동 필요
- **가격 미제공** → 식당 추천 시 가격 필터가 동작하지 않을 수 있음

---

## 3. 알림 채널 선택 가이드

| 채널 | 구현 상태 | 난이도 | 비용 | 적합한 경우 |
|------|-----------|--------|------|-------------|
| **CLI/앱 콘솔** | ✅ 구현됨 | ★☆☆ | 무료 | 개발·수동 확인 |
| **이메일 (SMTP)** | ✅ 구현됨 | ★★☆ | 무료~ | 정기 배치, 사내 메일 |
| **카카오톡 알림톡** | ❌ 미구현 | ★★★ | 건당 과금 | 팀원 휴대폰으로 자동 알림 |
| **앱 푸시 (FCM 등)** | ❌ 미구현 | ★★★ | 무료~ | 모바일/웹앱 구축 시 |

---

## 3-1. 콘솔 알림 (앱 자체) — 즉시 사용 가능

별도 API 없이 CLI에서 바로 확인합니다.

```powershell
# 의존성 설치 (최초 1회)
pip install -r requirements.txt

# Mock 데이터로 알림 테스트
python -m cli.main alerts --mock

# Kakao API 연동 후 실제 주변 검색
python -m cli.main alerts
```

출력 예:

```
[신규 오픈] 잠실맛집 한식당 (식당) - 서울 송파구 올림픽로 300 | 개업 5일차 | 평점 4.3
```

**Windows 작업 스케줄러**로 매일 아침 자동 실행 예:

```powershell
# 매일 09:00 실행 (경로는 본인 환경에 맞게 수정)
schtasks /create /tn "맛집알림" /tr "python -m cli.main alerts" /sc daily /st 09:00 /f
```

---

## 3-2. 이메일 알림 — SMTP 설정

`services/alert_service.py`에서 SMTP 발송을 지원합니다.

### Gmail 예시 (앱 비밀번호 필요)

1. Google 계정 → **보안** → **2단계 인증** 활성화
2. **앱 비밀번호** 생성 (메일 / 기타)
3. `.env` 설정:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=앱비밀번호_16자리
ALERT_RECIPIENT_EMAIL=수신자@fraunhofer.de
```

### Fraunhofer / Microsoft 365 예시

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=your.name@fraunhofer.de
SMTP_PASSWORD=계정비밀번호
ALERT_RECIPIENT_EMAIL=your.name@fraunhofer.de
```

### 발송 테스트

```powershell
python -m cli.main alerts --mock --email
```

---

## 3-3. 카카오톡 알림 — 별도 연동 필요

**현재 발급받은 Kakao REST API 키로는 카카오톡 메시지를 보낼 수 없습니다.**

### 옵션 A: 알림톡 (권장 — 서버 자동 발송)

| 단계 | 내용 |
|------|------|
| 1 | [카카오 비즈니스](https://business.kakao.com/) 채널 개설 + 비즈니스 채널 전환 |
| 2 | 공식 딜러사 가입 (예: [SOLAPI](https://solapi.com/), [NHN Cloud](https://www.ncloud.com/), 카카오엔터프라이즈) |
| 3 | 알림톡 **템플릿** 작성·심사 (정보성 메시지만 허용) |
| 4 | 딜러사 API로 발송 연동 |

예시 템플릿 문구:

```
[맛집탐방] 신규 오픈 알림
#{상호명} (#{유형})
주소: #{주소}
개업 #{N}일차
```

**예상 비용:** 건당 약 7~15원 (딜러사·템플릿 유형별 상이)

### 옵션 B: 카카오톡 "나에게 보내기" (개인용, 자동화 어려움)

- Kakao Login OAuth + 메시지 API 필요
- 사용자가 직접 로그인·동의해야 함
- **서버 배치 알림에는 부적합**

### 옵션 C: 카카오톡 공유 (수동)

- 사용자가 앱에서 "공유" 버튼을 눌러야 함
- 자동 알림 아님

### 향후 구현 시 권장 구조

```
AlertService
  ├── send_console_alerts()   ← 현재
  ├── send_email_alerts()     ← 현재
  └── send_kakao_alerts()     ← 알림톡 딜러사 API 연동 예정
```

---

## 3-4. 앱 푸시 알림 (모바일/웹앱 구축 시)

CLI가 아닌 **앱**을 만들 경우:

| 플랫폼 | 서비스 | 비고 |
|--------|--------|------|
| Android / iOS | Firebase Cloud Messaging (FCM) | 무료, 가장 일반적 |
| 웹 브라우저 | Web Push API + Service Worker | HTTPS 필수 |
| Windows 데스크톱 | Windows Toast Notification | Python `win10toast` 등 |

이 경우 백엔드에서 `AlertService.detect_new_openings()` 결과를 FCM 등으로 전달하면 됩니다.

---

## 4. (선택) Naver API — 평점·리뷰 보완

Kakao는 평점을 주지 않으므로, 추천 필터(평점 4+)를 실제 데이터로 쓰려면 Naver 연동이 필요합니다.

1. [Naver Cloud Platform](https://www.ncloud.com/) 가입
2. **Application Services → Maps** 신청
3. Client ID / Secret 발급

```env
NAVER_CLIENT_ID=발급_ID
NAVER_CLIENT_SECRET=발급_Secret
```

> Naver Provider는 아직 미구현입니다. 키만 미리 발급해 두면 이후 연동 시 바로 사용할 수 있습니다.

---

## 5. 전체 `.env` 예시

```env
# === 필수: Kakao Local API ===
KAKAO_REST_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === 사무실 좌표 (기본값과 다를 때만) ===
FRAUNHOFER_OFFICE_LAT=37.51692
FRAUNHOFER_OFFICE_LNG=127.10282

# === 필터 기준 (선택) ===
MIN_RATING=4.0
MAX_PRICE_PER_PERSON_KRW=15000
MAX_WALK_MINUTES=15
NEW_OPENING_DAYS=30

# === Naver (선택, 평점 보완용) ===
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

# === 이메일 알림 (선택) ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
ALERT_RECIPIENT_EMAIL=
```

---

## 6. CLI 명령어 요약

| 명령 | 기능 | API 필요 |
|------|------|----------|
| `python -m cli.main restaurants` | 맛집 추천 (평점 4+, 1.5만원↓, 도보 15분) | Kakao |
| `python -m cli.main cafes` | 카페 추천 (평점 4+, 도보 15분) | Kakao |
| `python -m cli.main alerts` | 신규 오픈 알림 (콘솔) | Kakao |
| `python -m cli.main alerts --email` | 신규 오픈 + 이메일 발송 | Kakao + SMTP |
| `python -m cli.main restaurants --mock` | Mock 데이터 테스트 | 불필요 |

---

## 7. 빠른 시작 체크리스트

- [ ] Kakao REST API 키 → `.env`의 `KAKAO_REST_API_KEY`
- [ ] 카카오맵 제품 활성화 (개발자 콘솔)
- [ ] `python -m cli.main restaurants` 로 검색 동작 확인
- [ ] (선택) SMTP 설정 후 `alerts --email` 테스트
- [ ] (선택) Naver API 키 발급 (평점 필터용)
- [ ] (향후) 알림톡 딜러사 계약 (카카오톡 자동 알림 원할 때)

---

## 8. 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `KAKAO_REST_API_KEY가 설정되지 않았습니다` | `.env` 없음/오타 | `.env` 파일 위치·변수명 확인 |
| `401 Unauthorized` | 잘못된 키 또는 카카오맵 미활성화 | 콘솔에서 REST API 키·카카오맵 ON 확인 |
| Mock 데이터만 나옴 | 키 미설정 | `.env`에 키 입력 후 재실행 |
| 추천 결과 0건 | Kakao 평점 미제공 → 필터 탈락 | `--mock`으로 테스트 또는 Naver 연동 대기 |
| 이메일 발송 실패 | SMTP 설정 오류 | Gmail은 앱 비밀번호 사용, 방화벽 587 포트 확인 |

---

## 9. 참고 링크

- [Kakao Local API 문서](https://developers.kakao.com/docs/latest/ko/local/dev-guide)
- [Kakao Developers 앱 관리](https://developers.kakao.com/console/app)
- [카카오 비즈니스 알림톡 가이드](https://kakaobusiness.gitbook.io/main/ad/infotalk)
- [Naver Cloud Maps](https://www.ncloud.com/product/applicationService/maps)
