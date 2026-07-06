"""하위 호환 — merge_near_commercial_seeds.py 사용."""

from scripts.merge_near_commercial_seeds import merge_seeds

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--no-crawl", action="store_true")
    args = parser.parse_args()
    merge_seeds(enable_crawl=not args.no_crawl)
