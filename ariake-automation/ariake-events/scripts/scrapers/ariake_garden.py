"""有明ガーデン（https://ariake.shopping-sumitomo-rd.com/event/）

取得方式：一覧ページ1枚に全件が載っている（WordPress、サーバー側で描画）。
  - カード：article.card02／タイトル：h2.cardTitle03／リンク：最初のa
  - 開催期間：data-periods 属性（JSON、飛び飛びの期間は複数）
  - カテゴリ：ul.label01 の各リンク文字列
  - 件数の検算：p.articleCount01 の「全N件」とカード数を照合
開催時間は一覧に載っていない（詳細ページのHTMLは未確認のため取得しない）。
"""
from __future__ import annotations

import json
from datetime import date

from bs4 import BeautifulSoup

from scripts import common as c

FACILITY_ID = "ariake_garden"
SOURCE_URL = "https://ariake.shopping-sumitomo-rd.com/event/"
MAX_DAYS = 150  # これより長い常設に近い掲載は店舗・サービス紹介とみなして除外


def parse(html: str) -> tuple[list[dict], list[str], int]:
    """(イベント, 除外ログ, ページ上のカード総数) を返す。"""
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("article.card02")
    count_node = soup.select_one("p.articleCount01 span")
    if count_node is None:
        raise ValueError("件数表示(p.articleCount01)が見つからない：ページ構造が変わった可能性")
    total = int(c.text_of(count_node))
    if total != len(cards):
        raise ValueError(f"カード数が表示件数と一致しない: {len(cards)} / {total}")
    events, notes = [], []
    for card in cards:
        title = c.clean_title(c.text_of(card.select_one("h2.cardTitle03")))
        a = card.select_one("a[href]")
        url = a["href"] if a else None
        cats = [c.text_of(x) for x in card.select("ul.label01 a")]
        try:
            periods = json.loads(card.get("data-periods") or "[]")
        except json.JSONDecodeError:
            periods = []
        if not title:
            notes.append("タイトルなしのカードを除外")
        elif not periods:
            notes.append(f"{title}：開催期間が特定できないため除外")
        elif "特集" in title:
            notes.append(f"{title}：特集記事のため除外")
        else:
            for p in periods:
                s, e = p.get("start"), p.get("end") or p.get("start")
                if c.is_date(s) and c.is_date(e) and (date.fromisoformat(e) - date.fromisoformat(s)).days > MAX_DAYS:
                    notes.append(f"{title}：{s}〜{e}は{MAX_DAYS}日を超える常設掲載のため除外")
                    continue
                events.append({"title": title, "start_date": s, "end_date": e,
                               "category": "・".join(cats) or None, "official_url": url})
    return events, notes, len(cards)


def scrape(session) -> c.ScrapeResult:
    html = c.fetch(session, SOURCE_URL).text
    events, notes, n_cards = parse(html)
    return c.ScrapeResult(events=events, pages=1, confirmed_empty=(n_cards == 0), notes=notes)
