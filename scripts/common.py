"""共通処理：取得・ID生成・検証・重複排除・安全なJSON書き込み。"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlsplit

import requests

log = logging.getLogger("ariake")
JST = timezone(timedelta(hours=9), "Asia/Tokyo")
USER_AGENT = "ariake-events-bot/1.0 (+https://github.com/ZOOMS-tec/ariake-events)"
FACILITY_IDS = ("tokyo_bigsight", "tokyo_garden_theater", "ariake_arena", "ariake_garden")
EVENT_KEYS = ("id", "facility_id", "title", "start_date", "end_date", "start_time", "end_time",
              "time_text", "category", "venue_detail", "description", "official_url",
              "source_url", "last_checked")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class FetchError(Exception):
    pass


@dataclass
class ScrapeResult:
    """施設別スクレイパーの戻り値。confirmed_empty は「公式サイト上で本当に0件」を確認できた場合のみTrue。"""
    events: list[dict] = field(default_factory=list)
    pages: int = 0
    confirmed_empty: bool = False
    notes: list[str] = field(default_factory=list)  # 登録対象か判断できず除外した情報などのログ


def today_jst() -> date:
    return datetime.now(JST).date()


def now_iso() -> str:
    return datetime.now(JST).replace(microsecond=0).isoformat()


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.5"})
    return s


def fetch(session: requests.Session, url: str, *, retries: int = 3, timeout: int = 20,
          interval: float = 1.0, backoff: float = 2.0) -> requests.Response:
    """GET。タイムアウト・指数バックオフ・アクセス間隔つき。4xxは再試行しない。"""
    last: Exception | None = None
    for i in range(retries):
        time.sleep(interval)
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code < 400:
                return r
            last = FetchError(f"HTTP {r.status_code}: {url}")
            if r.status_code < 500 and r.status_code != 429:
                break
        except requests.RequestException as e:
            last = e
        if i < retries - 1:
            wait = backoff ** i
            log.warning("再試行 %s/%s (%.0f秒後): %s", i + 1, retries, wait, url)
            time.sleep(wait)
    raise FetchError(str(last))


# ---------- 日付・ID ----------
def is_date(s) -> bool:
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def date_runs(dates: Iterable[str]) -> list[tuple[str, str]]:
    """連続する日付を (開始, 終了) にまとめる。飛び飛びの開催日は別の組になる。"""
    ds = sorted({date.fromisoformat(d) for d in dates})
    runs: list[list[date]] = []
    for d in ds:
        if runs and d - runs[-1][1] == timedelta(days=1):
            runs[-1][1] = d
        else:
            runs.append([d, d])
    return [(a.isoformat(), b.isoformat()) for a, b in runs]


def normalize_title(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "").lower()
    return re.sub(r"[\s\W_]+", "", t)


def normalize_url(u: str | None) -> str:
    """ID用：クエリ・フラグメント・末尾スラッシュを除く。"""
    if not u:
        return ""
    p = urlsplit(u.strip())
    return f"{p.scheme.lower()}://{p.netloc.lower()}{p.path.rstrip('/')}"


def make_event_id(facility_id: str, title: str, start_date: str, url: str | None = None,
                  session_key: str = "") -> str:
    """同じ内容なら実行のたびに同じID。同日の別公演は session_key（開演時刻など）で区別。"""
    key = "|".join([facility_id, normalize_title(title), start_date, normalize_url(url), session_key])
    return f"{facility_id}_{start_date.replace('-', '')}_{hashlib.sha1(key.encode()).hexdigest()[:8]}"


def normalize_event(raw: dict, last_checked: str | None = None) -> dict:
    e = {k: raw.get(k) for k in EVENT_KEYS}
    for k in e:
        if isinstance(e[k], str):
            e[k] = e[k].strip() or None
    if not e["end_date"]:
        e["end_date"] = e["start_date"]
    if not e["id"] and e["facility_id"] and e["title"] and e["start_date"]:
        e["id"] = make_event_id(e["facility_id"], e["title"], e["start_date"],
                                e["official_url"], raw.get("session_key", ""))
    e["last_checked"] = e["last_checked"] or last_checked
    return e


def validate_event(e: dict) -> list[str]:
    p = []
    if not e.get("id"):
        p.append("idなし")
    if e.get("facility_id") not in FACILITY_IDS:
        p.append(f"施設ID不正: {e.get('facility_id')}")
    if not isinstance(e.get("title"), str) or not e["title"].strip():
        p.append("イベント名なし")
    if not is_date(e.get("start_date")):
        p.append(f"開始日不正: {e.get('start_date')}")
    if not is_date(e.get("end_date")):
        p.append(f"終了日不正: {e.get('end_date')}")
    elif is_date(e.get("start_date")) and e["end_date"] < e["start_date"]:
        p.append("終了日が開始日より前")
    for k in ("start_time", "end_time"):
        if e.get(k) is not None and not TIME_RE.match(str(e[k])):
            p.append(f"{k}不正: {e[k]}")
    for k in ("official_url", "source_url"):
        if e.get(k) is not None and not re.match(r"^https?://", str(e[k])):
            p.append(f"{k}不正: {e[k]}")
    return p


def dedupe(events: list[dict]) -> tuple[list[dict], int]:
    """同じIDは1件に統合（空でない項目を優先）。"""
    out: dict[str, dict] = {}
    removed = 0
    for e in events:
        if e["id"] in out:
            removed += 1
            for k, v in e.items():
                if out[e["id"]].get(k) is None and v is not None:
                    out[e["id"]][k] = v
        else:
            out[e["id"]] = dict(e)
    return list(out.values()), removed


def drop_ended(events: list[dict], today: date) -> list[dict]:
    """終了日が今日より前のものを除く。開催中・開催前は残す。"""
    t = today.isoformat()
    return [e for e in events if e["end_date"] >= t]


def sort_events(events: list[dict]) -> list[dict]:
    order = {f: i for i, f in enumerate(FACILITY_IDS)}
    return sorted(events, key=lambda e: (e["start_date"], e["end_date"], order[e["facility_id"]], e["title"]))


# ---------- JSON ----------
def validate_document(doc) -> list[str]:
    """フロントエンド(js/app.js)が読める構造か検証する。"""
    if not isinstance(doc, dict):
        return ["ルートがオブジェクトではない"]
    p = []
    if not isinstance(doc.get("metadata"), dict):
        p.append("metadataなし")
    facs = doc.get("facilities")
    if not isinstance(facs, list) or not facs:
        p.append("facilitiesなし")
    elif any(not (isinstance(f, dict) and f.get("id") and f.get("name")) for f in facs):
        p.append("facilitiesの項目不足")
    if not isinstance(doc.get("events"), list):
        return p + ["eventsが配列ではない"]
    ids = set()
    for e in doc["events"]:
        pe = validate_event(e)
        if pe:
            p.append(f"{e.get('title')}: " + ", ".join(pe))
        if e.get("id") in ids:
            p.append(f"id重複: {e.get('id')}")
        ids.add(e.get("id"))
    return p


def load_document(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_document(old: dict, events: list[dict]) -> dict:
    meta = dict(old.get("metadata") or {})
    meta.update({"schema_version": meta.get("schema_version", "2.0"), "last_updated": now_iso(),
                 "timezone": "Asia/Tokyo"})
    return {"metadata": meta, "facilities": old["facilities"], "events": events}


def atomic_write_json(path: str, doc: dict) -> None:
    """一時ファイルに書いて検証し、成功したときだけ置き換える。失敗時は既存ファイルを触らない。"""
    problems = validate_document(doc)
    if problems:
        raise ValueError("JSON検証に失敗: " + "; ".join(problems[:5]))
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
        problems = validate_document(load_document(tmp))
        if problems:
            raise ValueError("書き込み後の検証に失敗: " + "; ".join(problems[:5]))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
