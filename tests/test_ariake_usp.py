from scripts import common as c
from scripts.scrapers import ariake_usp as u
from tests.helpers import FakeSession, fixture

BASE = "https://ariake-usp.com/event/"
SLUGS = ["FC5mxb0u", "20UR6uiX", "gUqu48gm"]
EVENT_SITEMAP = "https://ariake-usp.com/sitemap-dynamic/sitemap-dynamic-ZXZlbnQvOnNsdWc.xml"


def pages():
    idx = ("<sitemapindex><sitemap><loc>https://ariake-usp.com/sitemap-static.xml</loc></sitemap>"
           f"<sitemap><loc>{EVENT_SITEMAP}</loc></sitemap>"
           "<sitemap><loc>https://ariake-usp.com/sitemap-dynamic/sitemap-dynamic-bmV3cy86c2x1Zw.xml</loc></sitemap></sitemapindex>")
    xml = "<urlset>" + "".join(f"<url><loc>{BASE}{s}</loc></url>" for s in SLUGS) + "</urlset>"
    p = {u.SITEMAP_URL: idx, EVENT_SITEMAP: xml}
    for i, s in enumerate(SLUGS):
        p[BASE + s] = fixture(f"usp_detail_{i}.html")
    return p


def test_sitemap_name_decodes_base64():
    assert u.sitemap_name(EVENT_SITEMAP) == "event/:slug"
    assert u.sitemap_name("https://ariake-usp.com/sitemap-dynamic/sitemap-dynamic-bmV3cy86c2x1Zw.xml") == "news/:slug"
    assert u.sitemap_name("https://ariake-usp.com/sitemap-static.xml") is None


def test_parse_range_formats():
    assert u.parse_range("2026年10月11日(日)～12日(月・祝)") == ("2026-10-11", "2026-10-12")
    assert u.parse_range("2026年10月24日（土）") == ("2026-10-24", "2026-10-24")
    assert u.parse_range("2026年10月31日(土)～11月2日(月)") == ("2026-10-31", "2026-11-02")
    assert u.parse_range("2026年12月28日(月)～2027年1月3日(日)") == ("2026-12-28", "2027-01-03")
    assert u.parse_range("2026年12月28日～1月3日") == ("2026-12-28", "2027-01-03")  # 年またぎ
    assert u.parse_range("2026年10月11日(日)・12日(月)") is None  # 飛び飛びは推測しない
    assert u.parse_range("近日公開") is None and u.parse_range("") is None
    assert u.parse_range("2026年10月12日～10日") is None  # 終了が開始より前


def test_parse_real_detail_pages():
    got = {}
    for i, s in enumerate(SLUGS):
        ev, note = u.parse_detail(fixture(f"usp_detail_{i}.html"), BASE + s)
        assert note is None
        got[s] = ev
    assert (got["FC5mxb0u"]["start_date"], got["FC5mxb0u"]["end_date"]) == ("2026-10-11", "2026-10-12")
    assert "2nd Anniv. Fes" in got["FC5mxb0u"]["title"]
    assert (got["20UR6uiX"]["start_date"], got["20UR6uiX"]["end_date"]) == ("2026-10-15", "2026-10-23")
    assert "HYROX" in got["20UR6uiX"]["title"]
    assert (got["gUqu48gm"]["start_date"], got["gUqu48gm"]["end_date"]) == ("2026-10-24", "2026-10-24")
    assert got["gUqu48gm"]["official_url"] == BASE + "gUqu48gm"
    assert got["gUqu48gm"]["time_text"] is None and got["gUqu48gm"]["category"] is None


def test_slug_mismatch_and_missing_data_are_errors():
    for html, url in [(fixture("usp_detail_0.html"), BASE + "WRONG"), ("<html><body>x</body></html>", BASE + "a")]:
        try:
            u.parse_detail(html, url)
        except ValueError:
            continue
        raise AssertionError


def test_scrape_with_fake_session_and_valid_events():
    res = u.scrape(FakeSession(pages()))
    assert len(res.events) == 3 and res.pages == 5
    for e in res.events:
        n = c.normalize_event({**e, "facility_id": u.FACILITY_ID})
        assert c.validate_event(n) == []


def test_unreadable_page_is_logged_but_others_survive():
    p = pages()
    p[BASE + SLUGS[1]] = "<html><body>broken</body></html>"
    res = u.scrape(FakeSession(p))
    assert len(res.events) == 2 and any("読み取れず" in n for n in res.notes)


def test_all_pages_unreadable_or_no_event_sitemap_is_error():
    p = pages()
    for s in SLUGS:
        p[BASE + s] = "<html><body>broken</body></html>"
    for pp in (p, {u.SITEMAP_URL: "<sitemapindex></sitemapindex>"}):
        try:
            u.scrape(FakeSession(pp))
        except ValueError:
            continue
        raise AssertionError
