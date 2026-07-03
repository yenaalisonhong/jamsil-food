"""Kakao REST API 연결 테스트 (주소 좌표 + 주변 음식점 검색)."""

import sys
from pathlib import Path

# 프로젝트 루트를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from config.settings import get_settings


def main() -> int:
    settings = get_settings()
    key = settings.kakao_rest_api_key
    if not key:
        print("[FAIL] KAKAO_REST_API_KEY가 비어 있습니다. .env 파일에 키를 입력하세요.")
        return 1

    headers = {"Authorization": f"KakaoAK {key}"}
    address = "서울시 송파구 올림픽로 35가길 10 잠실더샵스타파크"

    print("1) 주소 → 좌표 변환 테스트")
    with httpx.Client(timeout=10.0) as client:
        r = client.get(
            "https://dapi.kakao.com/v2/local/search/address.json",
            headers=headers,
            params={"query": address},
        )
        if r.status_code != 200:
            print(f"   [FAIL] HTTP {r.status_code}: {r.text[:200]}")
            if r.status_code == 401:
                print("   → REST API 키 확인, 카카오맵 제품 활성화 여부 확인")
            return 1

        docs = r.json().get("documents", [])
        if not docs:
            print("   [FAIL] 주소 검색 결과 없음")
            return 1

        lat, lng = docs[0]["y"], docs[0]["x"]
        print(f"   [OK] {docs[0].get('address_name', address)}")
        print(f"      위도 {lat}, 경도 {lng}")

    print("\n2) 사무실 기준 음식점 검색 테스트")
    with httpx.Client(timeout=10.0) as client:
        r = client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            headers=headers,
            params={
                "query": "음식점",
                "x": settings.fraunhofer_office_lng,
                "y": settings.fraunhofer_office_lat,
                "radius": int(settings.max_walk_radius_meters),
                "category_group_code": "FD6",
                "size": 5,
            },
        )
        if r.status_code != 200:
            print(f"   [FAIL] HTTP {r.status_code}: {r.text[:200]}")
            return 1

        places = r.json().get("documents", [])
        print(f"   [OK] {len(places)}건 조회 (최대 5건 표시)")
        for p in places:
            print(f"      - {p['place_name']} ({p.get('distance', '?')}m)")

    print("\n[OK] Kakao API 연결 정상. 이제 다음을 실행하세요:")
    print("   python -m cli.main restaurants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
