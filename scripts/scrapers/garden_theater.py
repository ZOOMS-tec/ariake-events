"""東京ガーデンシアター のスクレイパー。

未実装：公式サイトの実際のHTML構造をまだ確認できていないため、セレクタを推測で書かない。
HTML収集ワークフロー(collect-html.yml)の結果をもとに実装する。
"""
from scripts.common import ScrapeResult

FACILITY_ID = "tokyo_garden_theater"
SOURCE_URL = "https://www.shopping-sumitomo-rd.com/tokyo_garden_theater/schedule/"


def scrape(session) -> ScrapeResult:
    raise NotImplementedError("東京ガーデンシアター：HTML構造を未確認のため未実装")
