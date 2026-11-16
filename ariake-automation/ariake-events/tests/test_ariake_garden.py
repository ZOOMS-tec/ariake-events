from scripts import common as c
from scripts.scrapers import ariake_garden as g
from tests.helpers import FakeSession, fixture


def test_parse_real_fixture():
    ev, notes, n = g.parse(fixture("ariake_garden.html"))
    assert n == 27 and len(ev) == 22
    first = ev[0]
    assert first["title"] == "Thanksママフォーラムmini" and first["start_date"] == "2026-11-25"
    assert "ワークショップ" in first["category"]
    assert all(c.is_date(e["start_date"]) and c.is_date(e["end_date"]) for e in ev)


def test_excludes_features_undated_and_long_running():
    _, notes, _ = g.parse(fixture("ariake_garden.html"))
    joined = "\n".join(notes)
    for word in ("クリスマスギフト特集", "パーティーグルメ特集", "見せてお得", "テイクアウト特集", "CARVINO", "マチルダ"):
        assert word in joined
    ev, _, _ = g.parse(fixture("ariake_garden.html"))
    assert "ARIAKE GARDEN Winter Illuminations" in [e["title"] for e in ev]  # 特集カテゴリでも催しは残す


def test_title_cleanup():
    ev, _, _ = g.parse(fixture("ariake_garden.html"))
    titles = [e["title"] for e in ev]
    assert "ARIAKE GARDEN BLACK FRIDAY" in titles  # ＜11/12更新＞を除去
    assert any(t.startswith("POP-UP ") for t in titles)


def test_non_contiguous_periods_become_separate_events():
    ev, _, _ = g.parse(fixture("ariake_garden.html"))
    bq = sorted((e["start_date"], e["end_date"]) for e in ev if "ブーケ" in e["title"])
    assert bq == [("2026-12-12", "2026-12-13"), ("2026-12-19", "2026-12-25")]
    ids = {c.normalize_event({**e, "facility_id": g.FACILITY_ID})["id"] for e in ev if "ブーケ" in e["title"]}
    assert len(ids) == 2


def test_count_mismatch_is_error():
    html = fixture("ariake_garden.html").replace("<span>27</span>", "<span>99</span>", 1)
    try:
        g.parse(html)
    except ValueError:
        return
    raise AssertionError("件数不一致を検出できていない")


def test_scrape_with_fake_session():
    res = g.scrape(FakeSession({g.SOURCE_URL: fixture("ariake_garden.html")}))
    assert res.pages == 1 and len(res.events) == 22
