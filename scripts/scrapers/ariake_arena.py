"""有明アリーナ のスクレイパー。

未実装：公式サイトの実際のHTML構造をまだ確認できていないため、セレクタを推測で書かない。
HTML収集ワークフロー(collect-html.yml)の結果をもとに実装する。
"""
from scripts.common import ScrapeResult

FACILITY_ID = "ariake_arena"
SOURCE_URL = "https://ariake-arena.tokyo/event/"


def scrape(session) -> ScrapeResult:
    raise NotImplementedError("有明アリーナ：HTML構造を未確認のため未実装")
