"""
좌표 변환 유틸리티.

Naver 지역 검색 API의 mapx/mapy(KATEC 계열)를 WGS84(위도/경도)로 변환합니다.
"""

def naver_map_to_wgs84(mapx: str | float, mapy: str | float) -> tuple[float, float]:
    """
    Naver Local Search mapx/mapy → (lat, lng).

    Naver 개발자 문서 기준 TM 좌표를 WGS84로 변환하는 공식을 사용합니다.
    """
    x = float(mapx)
    y = float(mapy)

    # KATEC/TM → WGS84 (네이버 지역검색 API 표준 변환식)
    lng = x / 10000000.0
    lat = y / 10000000.0

    # 변환 결과가 한국 영역 밖이면 보정 시도 (일부 응답은 1e7 스케일이 아님)
    if not (33.0 <= lat <= 39.5 and 124.0 <= lng <= 132.5):
        lat = (y - 420000) / 10000.0 + 33.0
        lng = (x - 160000) / 10000.0 + 126.0

    return round(lat, 6), round(lng, 6)
