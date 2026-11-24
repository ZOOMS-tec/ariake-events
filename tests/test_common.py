import json
from datetime import date

import pytest

from scripts import common as c
from scripts import main as m


def ev(**kw):
    base = {"facility_id": "ariake_arena", "title": "テスト公演", "start_date": "2026-12-01",
            "end_date": "2026-12-01", "official_url": "https://example.com/e/1?utm=a"}
    base.update(kw)
    return c.normalize_event(base, "2026-11-16T09:00:00+09:00")


def test_id_is_stable_and_ignores_query():
    a = c.make_event_id("ariake_arena", "テスト 公演", "2026-12-01", "https://x.jp/e/1?a=1#top")
    b = c.make_event_id("ariake_arena", "テスト　公演", "2026-12-01", "https://X.jp/e/1/?b=2")
    assert a == b
    assert a != c.make_event_id("ariake_arena", "テスト 公演", "2026-12-01", "https://x.jp/e/1", "18:00")


def test_date_runs_splits_non_consecutive():
    r = c.date_runs(["2026-12-12", "2026-12-13", "2026-12-19", "2026-12-25"])
    assert r == [("2026-12-12", "2026-12-13"), ("2026-12-19", "2026-12-19"), ("2026-12-25", "2026-12-25")]


def test_validate_event():
    assert c.validate_event(ev()) == []
    assert c.validate_event(ev(start_date="2026-13-01"))
    assert c.validate_event(ev(end_date="2026-11-30"))
    assert c.validate_event(ev(start_time="25:00"))
    assert c.validate_event(ev(official_url="javascript:x"))
    assert c.validate_event(ev(facility_id="other"))


def test_end_date_defaults_to_start_and_nulls_ok():
    e = c.normalize_event({"facility_id": "ariake_arena", "title": "A", "start_date": "2026-12-01"})
    assert e["end_date"] == "2026-12-01" and e["time_text"] is None and c.validate_event(e) == []


def test_dedupe_merges_and_keeps_same_day_sessions():
    a, b = ev(), ev(venue_detail="アリーナ")
    out, removed = c.dedupe([a, b])
    assert removed == 1 and out[0]["venue_detail"] == "アリーナ"
    night = c.normalize_event({"facility_id": "ariake_arena", "title": "テスト公演", "start_date": "2026-12-01",
                               "official_url": "https://example.com/e/1", "session_key": "19:00"})
    assert len(c.dedupe([ev(), night])[0]) == 2


def test_drop_ended_keeps_ongoing():
    es = [ev(start_date="2026-11-01", end_date="2026-11-15", title="終了"),
          ev(start_date="2026-11-10", end_date="2026-11-16", title="今日まで"),
          ev(start_date="2026-12-01", title="先")]
    assert [e["title"] for e in c.drop_ended(es, date(2026, 11, 16))] == ["今日まで", "先"]


def test_atomic_write_rejects_invalid_and_keeps_old(tmp_path):
    p = tmp_path / "events.json"
    good = {"metadata": {}, "facilities": [{"id": "ariake_arena", "name": "A"}], "events": [ev()]}
    c.atomic_write_json(str(p), good)
    before = p.read_text(encoding="utf-8")
    bad = {**good, "events": [ev(start_date="bad")]}
    with pytest.raises(ValueError):
        c.atomic_write_json(str(p), bad)
    assert p.read_text(encoding="utf-8") == before
    assert [f.name for f in tmp_path.iterdir()] == ["events.json"]


class Fake:
    def __init__(self, fid, events=None, exc=None, empty=False):
        self.FACILITY_ID, self.SOURCE_URL, self._e, self._x, self._z = fid, "https://example.com/", events or [], exc, empty

    def scrape(self, s):
        if self._x:
            raise self._x
        return c.ScrapeResult(events=self._e, pages=1, confirmed_empty=self._z)


def seed(tmp_path):
    p = tmp_path / "events.json"
    doc = {"metadata": {"schema_version": "2.0"}, "events": [ev(title="旧データ")],
           "facilities": [{"id": f, "name": f} for f in c.FACILITY_IDS]}
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


def raw(fid, title="新イベント"):
    return {"title": title, "start_date": "2099-01-01", "end_date": "2099-01-02"}


def test_main_keeps_json_when_any_facility_fails(tmp_path):
    p = seed(tmp_path)
    before = p.read_text(encoding="utf-8")
    sc = [("a", Fake("ariake_arena", [raw("x")])), ("b", Fake("ariake_garden", exc=RuntimeError("構造変更")))]
    assert m.run(str(p), scrapers=sc) == 1
    assert p.read_text(encoding="utf-8") == before


def test_main_fails_on_unexpected_zero_but_accepts_confirmed_zero(tmp_path):
    p = seed(tmp_path)
    assert m.run(str(p), scrapers=[("a", Fake("ariake_arena", []))]) == 1
    assert m.run(str(p), scrapers=[("a", Fake("ariake_arena", [], empty=True))]) == 0


def test_main_updates_and_dry_run_does_not(tmp_path):
    p = seed(tmp_path)
    before = p.read_text(encoding="utf-8")
    sc = [("a", Fake("ariake_arena", [raw("x"), raw("x")]))]
    assert m.run(str(p), dry_run=True, scrapers=sc) == 0
    assert p.read_text(encoding="utf-8") == before
    assert m.run(str(p), scrapers=sc) == 0
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert [e["title"] for e in doc["events"]] == ["新イベント"]  # 重複統合・旧データ置換
    assert doc["metadata"]["timezone"] == "Asia/Tokyo" and c.validate_document(doc) == []


def test_real_scrapers_fail_safely_on_network_error(tmp_path):
    from tests.helpers import FakeSession  # 全URLが404の状態
    p = seed(tmp_path)
    before = p.read_text(encoding="utf-8")
    orig = c.make_session
    c.make_session = lambda: FakeSession({})
    try:
        assert m.run(str(p)) == 1
    finally:
        c.make_session = orig
    assert p.read_text(encoding="utf-8") == before


def test_ensure_facilities_keeps_existing_and_adds_missing():
    cur = [{"id": "ariake_arena", "name": "有明アリーナ", "color": "#000000"}]
    out = c.ensure_facilities(cur)
    assert [f["id"] for f in out][0] == "ariake_arena" and out[0]["color"] == "#000000"  # 手動調整を保持
    assert {f["id"] for f in out} == set(c.FACILITY_IDS) and "ariake_usp" in c.FACILITY_IDS


def test_current_events_json_is_valid():
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "events.json")
    if os.path.exists(path):
        assert c.validate_document(c.load_document(path)) == []
