"""좌표 변환 테스트."""

from utils.coordinates import naver_map_to_wgs84


def test_naver_map_to_wgs84_jamsil_area() -> None:
    # 잠실 인근 대표 mapx/mapy (1e7 스케일)
    lat, lng = naver_map_to_wgs84("1271028200", "375169200")
    assert 37.0 < lat < 38.0
    assert 127.0 < lng < 128.0
