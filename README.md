# 잠실맛집 — Fraunhofer 근처 맛집·카페 탐색

프라운호퍼 한국사무소(잠실더샵스타파크) 기준 **도보 15분** 이내 맛집·카페를 수집·추천하는 도구입니다.

- **CLI**: 터미널에서 맛집/카페 추천, 신규 오픈 알림
- **웹 UI**: 지도·필터·점심 뽑기·식사 기록
- **데이터 파이프라인**: Kakao/Naver API + Naver Place 크롤링으로 `places.json` 갱신

기준 위치: 서울시 송파구 올림픽로 35가길 10, A동 202호 (위도 `37.51692`, 경도 `127.10282`)

---

## 빠른 시작

```powershell
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경 변수 설정
Copy-Item .env.example .env
# .env 에 KAKAO_REST_API_KEY (필수), NAVER_CLIENT_ID/SECRET (권장) 입력

# 3. CLI 테스트
python -m cli.main restaurants
python -m cli.main cafes
python -m cli.main alerts

# 4. 웹 UI (로컬)
python scripts/serve_site.py --open
# http://localhost:8765
```

API 키 발급·SMTP 알림 등 상세 설정은 [`docs/API_GUIDE.md`](docs/API_GUIDE.md)를 참고하세요.

---

## 기능 요약

| 구분 | 설명 |
|------|------|
| **기능 A** `restaurants` | 평점 4+, 인당 1.5만원 이하, 도보 15분 이내 맛집 |
| **기능 B** `cafes` | 평점 4+, 도보 15분 이내 카페 |
| **기능 C** `alerts` | 최근 30일 내 신규 오픈 식당·카페 알림 (`--email`로 SMTP 발송) |
| **웹 UI** | 지도·카테고리·키워드 필터, 신규 오픈 패널, 점심 뽑기 |
| **식사 기록** | `diary.html` — 방문 기록·평점, 4점 이상 맛집 모음 |

---

## CLI 명령어

```powershell
python -m cli.main restaurants          # 맛집 추천
python -m cli.main cafes                # 카페 추천
python -m cli.main alerts               # 신규 오픈 알림 (콘솔)
python -m cli.main alerts --email       # + 이메일 발송
python -m cli.main crawl <place_id>     # Naver Place 상세 크롤링
python -m cli.main add-price <key> <원> # 수동 가격 등록

# 옵션
python -m cli.main restaurants --mock      # Mock 데이터
python -m cli.main restaurants --no-crawl  # Naver 크롤링 비활성화
python -m cli.main -v                      # 상세 로그
```

---

## 웹 UI

| 경로 | 용도 |
|------|------|
| `site/` | 로컬 개발용 (정적 파일 + `/api/places` 라이브 API) |
| `docs/` | GitHub Pages 배포용 (`main` 브랜치 push 시 자동 배포) |

```powershell
# 로컬 서버 (site/ 기준, 실시간 API)
python scripts/serve_site.py --port 8765 --open

# 연결 확인
python scripts/verify_site.py
```

보충 스크립트(`supplement_*`, `merge_*`)는 `site/`와 `docs/`를 함께 갱신합니다. `export_places.py`는 기본 출력이 `site/data/places.json`이므로 Pages 반영 시 `docs/`에도 복사하거나 `--output docs/data/places.json`으로 한 번 더 실행하세요.

---

## 데이터 갱신 스크립트

### 전체 export

```powershell
python scripts/export_places.py
# 기본 출력: site/data/places.json
```

### 가까운 상가 5곳 심층 보충 (권장)

사무실에서 가장 가까운 상가 5곳(스타파크, 홈플러스, 장미상가, 장미아파트, 르엘)에 대해 키워드·업종·상호명 시드로 누락 매장을 보충합니다.

```powershell
python scripts/supplement_near_commercial.py --delay 15
```

Naver rate limit(429)이 발생하면 `--delay`를 늘리거나 몇 시간 뒤 재시도하세요.

### 기타 보충·갱신

```powershell
# 전체 상가 + 심층 5곳 우선
python scripts/supplement_commercial.py --delay 15

# 장미상가 전용 (하위 호환)
python scripts/supplement_jangmi.py --delay 15

# 수동 시드 병합
python scripts/merge_near_commercial_seeds.py   # data/near_commercial_seeds.json
python scripts/merge_jangmi_seeds.py          # data/jangmi_place_seeds.json
python scripts/merge_new_openings.py          # 신규 오픈 후보 병합

# places.json 필드 보강
python scripts/refresh_ratings_in_places_json.py
python scripts/refresh_menus_in_places_json.py
python scripts/refresh_prices_in_places_json.py
python scripts/backfill_reviews_in_places_json.py
python scripts/reclassify_places.py
```

### 수동 시드 추가

크롤링으로 잡히지 않는 매장은 `data/near_commercial_seeds.json`에 추가합니다.

```json
{
  "anchor": "장미상가",
  "name": "가보자식당",
  "naver_place_id": "",
  "lat": 37.51785,
  "lng": 127.10185,
  "address": "서울 송파구 ...",
  "category": "korean"
}
```

`anchor`는 `providers/jamsil_commercial.py`의 `COMMERCIAL_ANCHORS` 이름과 일치해야 합니다.

---

## 프로젝트 구조

```
cli/              Typer CLI (restaurants, cafes, alerts, crawl)
config/           설정 (사무실 좌표, 필터 기준, API 키)
models/           Place, Restaurant, Cafe 데이터 모델
providers/        Kakao, Naver API, Naver Map 목록, 상가 앵커
services/         추천·필터·크롤링·신규오픈 탐지·분류
scripts/          export, 보충 수집, 갱신, 로컬 서버
site/             웹 UI (로컬)
docs/             웹 UI (GitHub Pages)
data/             수동 시드, 캐시, manual_prices.json
tests/            pytest
```

---

## 데이터 소스

| 소스 | 역할 |
|------|------|
| **Kakao Local API** | 위치·거리 검색 (필수) |
| **Naver Search API** | 지역 검색, 블로그/뉴스 신규오픈 탐지 |
| **Naver Place 크롤링** | 평점, 메뉴가, 개업일, 리뷰 보강 |
| **수동 DB** | `data/manual_prices.json`, `data/manual_openings.json` |

Kakao만 설정하면 검색은 되지만 평점이 없어 필터 결과가 비어 있을 수 있습니다. Naver API·크롤링 설정을 권장합니다.

---

## 테스트

```powershell
python -m pytest -q
```

---

## 배포

`main` 브랜치에 push하면 `.github/workflows/pages.yml`이 `docs/` 폴더를 GitHub Pages에 배포합니다.

데이터를 갱신한 뒤 Pages에 반영하려면:

1. `python scripts/export_places.py` (또는 보충 스크립트)
2. `docs/data/places.json` 동기화 확인
3. `git add` → `commit` → `push`

---

## 라이선스·주의

- Naver Place 크롤링은 요청 간격(`CRAWL_REQUEST_DELAY_SEC`)을 지키고, 과도한 호출 시 IP rate limit(429)이 발생할 수 있습니다.
- API 키와 SMTP 비밀번호는 `.env`에만 보관하세요 (`.gitignore`에 포함됨).
