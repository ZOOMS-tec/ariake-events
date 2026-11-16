"""東京ビッグサイト（https://www.bigsight.jp/visitor/event/）

取得方式：一覧（10件/ページ）を「次へ」リンクが無くなるまでたどる。ページ数・総件数は固定しない。
  - イベント：article.lyt-event-01／タイトル：h3.hdg-01（リンクは主催者サイト）
  - 項目：dl.list-01（入場区分・利用施設・開催期間・開催時間・料金・URL）、dl.list-02（主催者・連絡先）
  - 検算：ページ上部の「検索結果 N件」と、たどって解析した件数を照合し、一致しなければ失敗
  - 有明GYM-EX など対象外の施設が利用施設に含まれるものは登録しない
2ページ目以降のHTMLは未確認（1ページ目と同じテンプレートと仮定し、件数の検算で保護）。
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scripts import common as c

FACILITY_ID = "tokyo_bigsight"
SOURCE_URL = "https://www.bigsight.jp/visitor/event/"
MAX_PAGES = 60
DATE_RE = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*[-－〜~]\s*(\d{1,2}):(\d{2})$")
EXCLUDE_VENUE = ("GYM-EX", "GYM‐EX", "有明GYM")


def parse(html: str, page_url: str) -> tuple[list[dict], list[str], int, str | None]:
    """(イベント, 除外ログ, ページ上のイベント数, 次ページURL) を返す。総件数は parse_total で取る。"""
    soup = BeautifulSoup(html, "lxml")
    arts = soup.select("article.lyt-event-01")
    events, notes = [], []
    for art in arts:
        h = art.select_one("h3.hdg-01")
        if h is None:
            raise ValueError("イベント名(h3.hdg-01)が見つからない")
        title = re.sub(r"新規タブで開きます", "", c.text_of(h)).strip()
        f = {c.text_of(r.dt): r.dd for r in art.select("dl.list-01 > div, dl.list-02 > div") if r.dt and r.dd}
        val = lambda k: c.text_of(f[k]) if k in f else None
        venue = val("利用施設")
        if venue and any(x in venue for x in EXCLUDE_VENUE):
            notes.append(f"{title}：対象外施設（{venue}）のため除外")
            continue
        dates = DATE_RE.findall(val("開催期間") or "")
        if not dates:
            raise ValueError(f"開催期間を読み取れない: {title}")
        iso = [f"{int(y):04d}-{int(m):02d}-{int(d):02d}" for y, m, d in dates]
        start, end = iso[0], iso[-1]
        time_text = val("開催時間")
        tm = TIME_RE.match(time_text or "")
        link = h.select_one("a[href]") or (f["URL"].select_one("a[href]") if "URL" in f else None)
        desc = [x for x in (f"入場料：{val('料金')}" if val("料金") else None,
                            f"主催：{val('主催者')}" if val("主催者") else None) if x]
        events.append({
            "title": title, "start_date": start, "end_date": end, "time_text": time_text,
            "start_time": f"{int(tm[1]):02d}:{tm[2]}" if tm and start == end else None,
            "end_time": f"{int(tm[3]):02d}:{tm[4]}" if tm and start == end else None,
            "category": val("入場区分"), "venue_detail": venue,
            "description": "／".join(desc) or None,
            "official_url": link["href"] if link and link["href"].startswith("http") else None,
        })
    nxt = soup.select_one("p.next a.next[href]")
    return events, notes, len(arts), urljoin(page_url, nxt["href"]) if nxt else None


def parse_total(html: str) -> int:
    b = BeautifulSoup(html, "lxml").select_one(".hdg-search-01 b")
    if b is None or not c.text_of(b).isdigit():
        raise ValueError("検索結果の総件数(.hdg-search-01 b)が見つからない：ページ構造が変わった可能性")
    return int(c.text_of(b))


def scrape(session) -> c.ScrapeResult:
    url, seen, events, notes, n_arts, total = SOURCE_URL, set(), [], [], 0, None
    while url:
        if url in seen or len(seen) >= MAX_PAGES:
            raise ValueError("ページ送りがループ、または上限を超えた")
        seen.add(url)
        html = c.fetch(session, url).text
        if total is None:
            total = parse_total(html)
        ev, nt, n, url = parse(html, url)
        events += ev
        notes += nt
        n_arts += n
    if n_arts != total:
        raise ValueError(f"解析件数が検索結果の総件数と一致しない: {n_arts} / {total}")
    return c.ScrapeResult(events=events, pages=len(seen), confirmed_empty=(total == 0), notes=notes)
