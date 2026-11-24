"""有明アーバンスポーツパーク（https://ariake-usp.com/event）

一覧ページ(/event)は、イベント一覧をブラウザ側のJavaScriptで読み込むため、HTMLには一覧が入っていない。
そのため次の方式をとる（通常のHTTP取得のみ。非公開APIやブラウザ自動操作は使わない）。
  1. サイトマップ(sitemap.xml)から、イベント詳細ページ用のサイトマップ（名前が base64 で「event/:slug」）を探す
  2. そこに載っている各イベント詳細ページ(/event/<slug>)を取得する
  3. 詳細ページのHTMLに埋め込まれたNuxtのデータ(script#__NUXT_DATA__)から、
     タイトル(title)・開催日の文字列（日付表記を含む項目）・slugを読む
開催時間・カテゴリは構造化されていないため取得しない（null）。本文の自由記述から推測しない。
"""
from __future__ import annotations

import base64
import json
import re

from bs4 import BeautifulSoup

from scripts import common as c

FACILITY_ID = "ariake_usp"
SOURCE_URL = "https://ariake-usp.com/event"
SITEMAP_URL = "https://ariake-usp.com/sitemap.xml"
MAX_DETAIL_PAGES = 300
LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
START_RE = re.compile(r"\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")
END_RE = re.compile(r"\s*[～〜~\-－ー]\s*(?:(\d{4})年\s*)?(?:(\d{1,2})月\s*)?(\d{1,2})日")
SKIP_KEYS = {"slug", "cover", "title", "body", "_meta", "_filter", "id"}


def sitemap_name(url: str) -> str | None:
    """sitemap-dynamic-<base64>.xml の <base64> を復号する（例：event/:slug）。"""
    m = re.search(r"sitemap-dynamic-([A-Za-z0-9_-]+)\.xml", url)
    if not m:
        return None
    b = m.group(1)
    try:
        return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode("utf-8")
    except Exception:
        return None


def parse_range(text: str) -> tuple[str, str] | None:
    """「2026年10月11日(日)～12日(月・祝)」などを (開始, 終了) にする。確信が持てない表記は None。"""
    text = re.sub(r"[（(][^）)]*[）)]", "", text or "")  # 曜日・祝日の括弧「(日)」「（月・祝）」を除く
    m = START_RE.match(text)
    if not m:
        return None
    y, mo, d = int(m[1]), int(m[2]), int(m[3])
    start, rest = (y, mo, d), text[m.end():]
    end = start
    e = END_RE.match(rest)
    if e:
        ey = int(e[1]) if e[1] else y
        em = int(e[2]) if e[2] else mo
        if not e[1] and e[2] and em < mo:
            ey += 1  # 年またぎ（12月→1月）
        end = (ey, em, int(e[3]))
        rest = rest[e.end():]
    if re.search(r"\d{1,2}\s*日", rest):  # 「・」区切りの飛び飛びの日付など、複雑な表記は登録しない
        return None
    iso = lambda t: f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"
    s, en = iso(start), iso(end)
    return (s, en) if c.is_date(s) and c.is_date(en) and en >= s else None


def parse_detail(html: str, url: str) -> tuple[dict | None, str | None]:
    """(イベント or None, 除外・要確認のログ or None)。構造が読めないページは ValueError。"""
    soup = BeautifulSoup(html, "lxml")
    sc = soup.find("script", id="__NUXT_DATA__")
    if sc is None or not sc.string:
        raise ValueError(f"__NUXT_DATA__が見つからない: {url}")
    data = json.loads(sc.string)
    slug_in_url = url.rstrip("/").rsplit("/", 1)[-1]
    node = next((v for v in data if isinstance(v, dict) and {"slug", "title", "body"} <= v.keys()), None)
    if node is None:
        raise ValueError(f"イベントのデータ(slug/title/body)が見つからない: {url}")

    def val(i):
        return data[i] if isinstance(i, int) and 0 <= i < len(data) else None

    title = c.clean_title(val(node["title"]) if isinstance(val(node["title"]), str) else "")
    if val(node["slug"]) != slug_in_url:
        raise ValueError(f"URLとデータのslugが一致しない: {url}")
    # 開催日の項目名はStudio側が自動生成した名前のため固定せず、日付表記で始まる文字列の項目を探す
    date_text = next((val(i) for k, i in node.items() if k not in SKIP_KEYS
                      and isinstance(val(i), str) and START_RE.match(val(i))), None)
    if not title:
        return None, f"{url}：タイトルなしのため除外"
    if not date_text:
        return None, f"{title}（{url}）：開催日の項目が見つからないため除外"
    rng = parse_range(date_text)
    if rng is None:
        return None, f"{title}（{url}）：日付表記を確定できないため除外「{date_text}」"
    return {"title": title, "start_date": rng[0], "end_date": rng[1], "official_url": url,
            "source_url": SOURCE_URL, "time_text": None, "category": None}, None


def scrape(session) -> c.ScrapeResult:
    index = c.fetch(session, SITEMAP_URL).text
    maps = [u for u in LOC_RE.findall(index) if sitemap_name(u) == "event/:slug"]
    if not maps:
        raise ValueError("サイトマップにイベント用(event/:slug)が見つからない：構造が変わった可能性")
    urls: list[str] = []
    for m in maps:
        urls += [u for u in LOC_RE.findall(c.fetch(session, m).text) if "/event/" in u]
    urls = list(dict.fromkeys(urls))
    if len(urls) > MAX_DETAIL_PAGES:
        raise ValueError(f"詳細ページが{len(urls)}件と多すぎる（上限{MAX_DETAIL_PAGES}）：取得方法の見直しが必要")
    events, notes, ok = [], [], 0
    for u in urls:
        try:
            ev, note = parse_detail(c.fetch(session, u).text, u)
            ok += 1
        except (ValueError, json.JSONDecodeError, c.FetchError) as e:
            notes.append(f"{u}：読み取れず除外（{e}）")
            continue
        if ev:
            events.append(ev)
        if note:
            notes.append(note)
    if urls and ok == 0:
        raise ValueError("すべての詳細ページで読み取りに失敗：ページ構造が変わった可能性")
    return c.ScrapeResult(events=events, pages=2 + len(urls), confirmed_empty=(not urls), notes=notes)
