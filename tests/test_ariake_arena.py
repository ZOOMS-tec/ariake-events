from scripts import common as c
from scripts.scrapers import ariake_arena as a
from tests.helpers import FakeSession, fixture


def parsed():
    return a.parse(fixture("ariake_arena.html"), a.SOURCE_URL)


def test_parse_real_fixture():
    ev, notes, links = parsed()
    assert len(ev) == 7 and len(links) == 5
    glay = [e for e in ev if "GLAY" in e["title"]][0]
    assert (glay["start_date"], glay["end_date"]) == ("2026-11-28", "2026-11-29")
    assert "11/28 開場 16:00 / 開演 17:00" in glay["time_text"] and "11/29 開場 15:00 / 開演 16:00" in glay["time_text"]


def test_year_inferred_across_month_boundary():
    ev, _, _ = parsed()
    mr = [e for e in ev if "Mr.Children" in e["title"]][0]
    assert (mr["start_date"], mr["end_date"]) == ("2026-10-31", "2026-11-01")


def test_two_sessions_per_day_are_kept():
    ev, _, _ = parsed()
    hl = [e for e in ev if "HiGH&LOW" in e["title"]][0]
    assert hl["time_text"].count("①") == 2 and hl["time_text"].count("②") == 2
    assert hl["start_time"] is None  # 複数公演・複数日は代表時刻を決めない


def test_single_day_start_time_and_no_time_info():
    ev, _, _ = parsed()
    b = [e for e in ev if "BALLISTIK" in e["title"]][0]
    assert b["start_time"] == "17:00"
    sls = [e for e in ev if e["title"] == "SLS TOKYO 2026"][0]
    assert sls["time_text"] is None  # 「公式サイトをご覧ください」は時間情報ではない


def test_title_when_subtitle_is_a_notice():
    ev, _, _ = parsed()
    assert "HiGH&LOW THE 戦国 LOVE&HATE" in [e["title"] for e in ev]


def test_non_contiguous_dates_are_split():
    html = fixture("ariake_arena.html").replace("<span>11.19 THU</span>", "<span>11.25 WED</span>", 1) if "<span>11.19 THU</span>" in fixture("ariake_arena.html") else None
    if html:
        ev, _, _ = a.parse(html, a.SOURCE_URL)
        runs = sorted((e["start_date"], e["end_date"]) for e in ev if "HiGH&LOW" in e["title"])
        assert runs == [("2026-11-18", "2026-11-18"), ("2026-11-25", "2026-11-25")]
    assert c.date_runs(["2026-11-18", "2026-11-25"]) == [("2026-11-18", "2026-11-18"), ("2026-11-25", "2026-11-25")]


def test_scrape_all_month_pages_and_structure_error():
    html = fixture("ariake_arena.html")
    pages = {u: html for u in ["https://ariake-arena.tokyo/event/", "https://ariake-arena.tokyo/event/next/",
                               "https://ariake-arena.tokyo/event/two/", "https://ariake-arena.tokyo/event/three/",
                               "https://ariake-arena.tokyo/event/last/"]}
    res = a.scrape(FakeSession(pages))
    assert res.pages == 5
    try:
        a.parse("<html><body>x</body></html>", a.SOURCE_URL)
    except ValueError:
        return
    raise AssertionError
