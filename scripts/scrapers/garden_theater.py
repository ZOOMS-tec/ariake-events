"""東京ガーデンシアター（https://www.shopping-sumitomo-rd.com/tokyo_garden_theater/schedule/）

取得方式：月別ページ（?date=YYYY-MM）をたどる。
  - 月リンク：nav.nav_scheduleMonthLink a／さらに先の月：nav_scheduleMonthPagenation の「次の期間」リンク
  - 公演：ul.list_schedule > li（.ymd .m/.d は月日のみ。年は表示中の月ページから決める）
  - 非公開の予定（タイトル・出演者が「Private」）は登録しない
開場・開演時間は詳細ページにあると思われるが、詳細ページのHTMLは未確認のため取得しない。
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from scripts import common as c

FACILITY_ID = "tokyo_garden_theater"
SOURCE_URL = "https://www.shopping-sumitomo-rd.com/tokyo_garden_theater/schedule/"
MAX_PAGES = 24


def month_of(url: str) -> str | None:
    q = parse_qs(urlsplit(url).query).get("date", [None])[0]
    return q if q and re.fullmatch(r"\d{4}-\d{2}", q) else None


def parse(html: str, page_url: str) -> tuple[list[dict], list[str], list[str]]:
    """(イベント, 除外ログ, たどるべき他ページのURL) を返す。"""
    soup = BeautifulSoup(html, "lxml")
    ul = soup.select_one("ul.list_schedule")
    active = soup.select_one(".nav_scheduleMonthLink li.-active a[href]")
    ym = (month_of(active["href"]) if active else None) or month_of(page_url)
    month_nav = soup.select_one("nav.nav_scheduleMonth")
    if ul is None and month_nav is None:
        raise ValueError("公演一覧(ul.list_schedule)も月ナビ(nav.nav_scheduleMonth)も見つからない：ページ構造が変わった可能性")
    if not ym and ul is not None:
        raise ValueError("表示中の年月を判定できない")
    links = [urljoin(page_url, a["href"]).split("#")[0]
             for a in soup.select(".nav_scheduleMonthLink a[href], .nav_scheduleMonthPagenation a[href]")]
    events, notes = [], []
    if ul is None:  # 月ナビはあるが公演一覧の枠がない＝その月は公演なし、と扱う
        notes.append(f"{ym or page_url}：公演一覧の枠なし（0件として扱う）")
        return events, notes, links
    year, month = int(ym[:4]), int(ym[5:])
    for li in ul.select(":scope > li"):
        m, d = c.text_of(li.select_one(".ymd .m")), c.text_of(li.select_one(".ymd .d"))
        title, player = c.text_of(li.select_one(".title")), c.text_of(li.select_one(".player"))
        if not (m.isdigit() and d.isdigit()):
            raise ValueError(f"日付を読み取れない公演がある: {title}")
        if title.lower() == "private" or (not title and player.lower() == "private"):
            notes.append(f"{ym} {m}/{d}：非公開(Private)の予定のため除外")
            continue
        y = year + 1 if int(m) < month else year
        a = li.select_one("a[href]")
        events.append({
            "title": title, "start_date": f"{y:04d}-{int(m):02d}-{int(d):02d}",
            "category": c.text_of(li.select_one(".tag")) or None,
            "description": f"出演：{player}" if player and player != title else None,
            "official_url": urljoin(page_url, a["href"]) if a else None,
        })
    return events, notes, links


def scrape(session) -> c.ScrapeResult:
    queue, seen, events, notes = [SOURCE_URL], set(), [], []
    while queue:
        url = queue.pop(0)
        key = month_of(url) or "default"
        if key in seen:
            continue
        if len(seen) >= MAX_PAGES:
            raise ValueError("ページ数が上限を超えた（ループの可能性）")
        seen.add(key)
        try:
            ev, nt, links = parse(c.fetch(session, url).text, url)
        except ValueError as e:
            raise ValueError(f"{e} [{url}]") from e
        events += ev
        notes += nt
        queue += [u for u in links if (month_of(u) or "default") not in seen]
    # 月ページの重複（既定ページと?date=当月）はID統合で1件になる
    return c.ScrapeResult(events=events, pages=len(seen), confirmed_empty=False, notes=notes)
