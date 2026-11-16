import re

from scripts import common as c
from scripts.scrapers import bigsight as b
from tests.helpers import FakeSession, fixture


def test_parse_real_fixture():
    ev, notes, n, nxt = b.parse(fixture("bigsight.html"), b.SOURCE_URL)
    assert n == 10 and len(ev) == 10 and nxt == "https://www.bigsight.jp/visitor/event/search.php?page=2"
    e = ev[0]
    assert e["title"] == "ハウスクリーニング展"  # 「新規タブで開きます」を除去
    assert (e["start_date"], e["end_date"]) == ("2026-11-18", "2026-11-19")
    assert e["venue_detail"] == "南1・2ホール" and e["time_text"] == "10:00-17:00" and e["official_url"] == "https://bmcl.jma.or.jp/"
    assert e["start_time"] is None  # 複数日は時刻を代表値にしない
    assert "入場料：無料 (要登録)" in e["description"] and "主催：" in e["description"]


def test_total_count_read_from_page():
    assert b.parse_total(fixture("bigsight.html")) == 184


def test_gym_ex_events_are_excluded():
    html = fixture("bigsight.html").replace("南1・2ホール", "有明GYM-EX", 1)
    ev, notes, n, _ = b.parse(html, b.SOURCE_URL)
    assert n == 10 and len(ev) == 9 and "GYM-EX" in notes[0]


def _two_pages():
    p1 = re.sub(r"<b>\s*184\s*</b>", "<b>20</b>", fixture("bigsight.html"))
    p2 = re.sub(r'<p class="next">.*?</p>', "", p1, flags=re.S)
    return {b.SOURCE_URL: p1, "https://www.bigsight.jp/visitor/event/search.php?page=2": p2}


def test_scrape_follows_pagination_until_no_next():
    sess = FakeSession(_two_pages())
    res = b.scrape(sess)
    assert res.pages == 2 and len(res.events) == 20


def test_count_mismatch_is_error():
    pages = _two_pages()
    pages[b.SOURCE_URL] = pages[b.SOURCE_URL].replace("<b>20</b>", "<b>99</b>", 1)
    try:
        b.scrape(FakeSession(pages))
    except ValueError as e:
        assert "一致しない" in str(e)
        return
    raise AssertionError


def test_events_are_valid_for_json():
    ev, _, _, _ = b.parse(fixture("bigsight.html"), b.SOURCE_URL)
    for e in ev:
        n = c.normalize_event({**e, "facility_id": b.FACILITY_ID})
        assert c.validate_event(n) == []
