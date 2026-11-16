"""有明ガーデン のスクレイパー。

未実装：公式サイトの実際のHTML構造をまだ確認できていないため、セレクタを推測で書かない。
HTML収集ワークフロー(collect-html.yml)の結果をもとに実装する。
"""
from scripts.common import ScrapeResult

FACILITY_ID = "ariake_garden"
SOURCE_URL = "https://ariake.shopping-sumitomo-rd.com/event/"


def scrape(session) -> ScrapeResult:
    raise NotImplementedError("有明ガーデン：HTML構造を未確認のため未実装")
