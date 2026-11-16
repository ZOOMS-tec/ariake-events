from scripts.scrapers import garden_theater as t
from tests.helpers import FakeSession, fixture

BASE = "https://www.shopping-sumitomo-rd.com/tokyo_garden_theater/schedule/"


def test_parse_real_fixture_and_private_excluded():
    ev, notes, links = t.parse(fixture("garden_theater.html"), BASE)
    assert [e["start_date"] for e in ev] == ["2026-11-17", "2026-11-18", "2026-11-21", "2026-11-22", "2026-11-28"]
    assert any("Private" in n for n in notes)
    assert ev[0]["title"].startswith("Da-iCE") and ev[0]["category"] == "コンサート・ショー"
    assert ev[0]["official_url"].endswith("/schedule/5646/")
    assert ev[0]["description"] == "出演：Da-iCE"


def test_month_navigation_links_found():
    _, _, links = t.parse(fixture("garden_theater.html"), BASE)
    assert any("date=2026-12" in u for u in links) and any("date=2027-05" in u for u in links)


def test_scrape_follows_months_and_dedupes_pages():
    html = fixture("garden_theater.html")
    dec = html.replace('<li class="-active">', '<li class="">', 1).replace(
        '<li class="">\n<a href="/tokyo_garden_theater/schedule/?date=2026-12#nav">',
        '<li class="-active"><a href="/tokyo_garden_theater/schedule/?date=2026-12#nav">', 1)
    pages = {BASE: html}
    for u in ["?date=2026-11", "?date=2026-12", "?date=2027-01", "?date=2027-02", "?date=2027-03", "?date=2027-04", "?date=2027-05"]:
        pages[BASE + u] = dec if u == "?date=2026-12" else html.replace("2026-11</a>", "x</a>") if False else dec
    sess = FakeSession(pages)
    res = t.scrape(sess)
    assert res.pages >= 7  # 既定ページ＋月リンク＋「次の期間」を取得
    assert len(set(sess.requested)) == len(sess.requested)  # 同じページを二度取得しない


def test_missing_list_is_error():
    try:
        t.parse("<html><body><p>error</p></body></html>", BASE)
    except ValueError:
        return
    raise AssertionError
