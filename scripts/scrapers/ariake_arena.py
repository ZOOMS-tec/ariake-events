"""有明アリーナ（https://ariake-arena.tokyo/event/）

取得方式：月別ページ（/event/、/event/next/ …）をたどる。
  - 月リンク：nav.event_tab_menu a／表示月：li.active の .year と .month_number
  - 公演：ul.event_detail_list > li（日付は「10.31 SAT」形式で年なし。表示月に最も近い年を採用）
  - 公演時間：table.detail_table の「公演時間」行（日別・複数公演の行をそのまま保持）
  - 公式サイト：a.other_link（主催者等のサイト）。ない場合は null
一覧に載っていない月ページのHTMLは未確認だが、同一テンプレートの月ナビがある限り同じ構造として扱う。
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from scripts import common as c

FACILITY_ID = "ariake_arena"
SOURCE_URL = "https://ariake-arena.tokyo/event/"
MAX_PAGES = 18
MD_RE = re.compile(r"(\d{1,2})\.(\d{1,2})")
LINE_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\s*[A-Za-z]{3}\.?\s*(.*)$")


def pick_year(py: int, pm: int, m: int, d: int) -> int:
    base = date(py, pm, 1)
    return min((py - 1, py, py + 1), key=lambda y: abs((date(y, m, d) - base).days))


def td_lines(td) -> list[str]:
    for br in td.find_all("br"):
        br.replace_with("\n")
    return [re.sub(r"\s+", " ", x).strip() for x in td.get_text().split("\n") if x.strip()]


def parse(html: str, page_url: str) -> tuple[list[dict], list[str], list[str]]:
    soup = BeautifulSoup(html, "lxml")
    nav = soup.select_one("nav.event_tab_menu")
    active = soup.select_one("nav.event_tab_menu li.active")
    if nav is None or active is None:
        raise ValueError("月ナビ(nav.event_tab_menu)が見つからない：ページ構造が変わった可能性")
    py, pm = int(c.text_of(active.select_one(".year"))), int(c.text_of(active.select_one(".month_number")))
    links = [a["href"] for a in nav.select("a[href]")]
    notes, events = [], []
    ul = soup.select_one("ul.event_detail_list")
    if ul is None:
        notes.append(f"{py}-{pm:02d}：公演一覧なし（0件として扱う）")
        return events, notes, links
    for li in ul.select(":scope > li"):
        name = c.text_of(li.select_one(".event_name p"))
        sub = c.text_of(li.select_one(".sub_title"))
        if sub and not re.search(r"ご確認|ご覧ください|※", sub):
            norm = lambda s: re.sub(r"\W+", "", s).lower()
            title = sub if (not name or norm(name) in norm(sub)) else f"{name} {sub}"
        else:
            title = name
        days = sorted({date(pick_year(py, pm, int(m), int(d)), int(m), int(d)).isoformat()
                       for t in [c.text_of(s) for s in li.select(".event_day span")] for m, d in MD_RE.findall(t)[:1]})
        if not title or not days:
            raise ValueError(f"タイトルまたは日付を読み取れない公演: {li.get('id')}")
        rows = {c.text_of(r.th): r.td for r in li.select("table.detail_table tr") if r.th and r.td}
        # 日別の公演時間（複数公演の行も保持）
        by_day: dict[str, list[str]] = {}
        common_lines: list[str] = []
        if "公演時間" in rows:
            cur = None
            for ln in td_lines(rows["公演時間"]):
                m = LINE_DATE_RE.match(ln)
                if m:
                    cur = date(pick_year(py, pm, int(m[1]), int(m[2])), int(m[1]), int(m[2])).isoformat()
                    by_day.setdefault(cur, [])
                    if m[3]:
                        by_day[cur].append(m[3])
                elif re.search(r"開場|開演", ln):
                    (by_day[cur] if cur else common_lines).append(ln)
        price = " ／ ".join(td_lines(rows["料金"])) if "料金" in rows else None
        link = li.select_one("a.other_link")
        for s, e in c.date_runs(days):
            run_days = [d for d in days if s <= d <= e]
            parts = []
            for d in run_days:
                sess = by_day.get(d) or common_lines
                if sess:
                    label = "" if len(run_days) == 1 else f"{int(d[5:7])}/{int(d[8:])} "
                    parts.append(label + " ".join(sess))
            time_text = "｜".join(parts) or None
            starts = re.findall(r"開演\s*(\d{1,2}):(\d{2})", time_text or "")
            single = len(run_days) == 1 and len(starts) == 1
            events.append({
                "title": title, "start_date": s, "end_date": e, "time_text": time_text,
                "start_time": f"{int(starts[0][0]):02d}:{starts[0][1]}" if single else None,
                "category": None,
                "description": f"料金：{price}" if price else None,
                "official_url": link["href"] if link and link.get("href", "").startswith("http") else None,
                "venue_detail": None,
            })
    return events, notes, links


def scrape(session) -> c.ScrapeResult:
    from urllib.parse import urljoin
    queue, seen, events, notes = [SOURCE_URL], set(), [], []
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        if len(seen) >= MAX_PAGES:
            raise ValueError("ページ数が上限を超えた（ループの可能性）")
        seen.add(url)
        ev, nt, links = parse(c.fetch(session, url).text, url)
        events += ev
        notes += nt
        queue += [urljoin(url, u) for u in links if urljoin(url, u) not in seen]
    return c.ScrapeResult(events=events, pages=len(seen), confirmed_empty=False, notes=notes)
