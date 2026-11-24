"""イベント取得のエントリポイント。

  python -m scripts.main --dry-run   取得・検証だけ行い events.json は変更しない
  python -m scripts.main             全施設が成功した場合のみ events.json を更新
"""
from __future__ import annotations

import argparse
import logging
import sys

from scripts import common as c
from scripts.scrapers import ariake_arena, ariake_garden, ariake_usp, bigsight, garden_theater

SCRAPERS = [("東京ビッグサイト", bigsight), ("東京ガーデンシアター", garden_theater),
            ("有明アリーナ", ariake_arena), ("有明ガーデン", ariake_garden),
            ("有明アーバンスポーツパーク", ariake_usp)]
log = logging.getLogger("ariake")
DROP_WARN_RATIO = 0.5  # 前回の半分以下になったら警告（失敗とは判断しない）


def run(path: str = "events.json", dry_run: bool = False, scrapers=None) -> int:
    scrapers = scrapers or SCRAPERS
    old = c.load_document(path)
    prev: dict[str, int] = {}
    for e in old.get("events", []):
        prev[e["facility_id"]] = prev.get(e["facility_id"], 0) + 1
    session, stamp, today = c.make_session(), c.now_iso(), c.today_jst()
    rows, events, failed = [], [], False

    for name, mod in scrapers:
        log.info("[%s] 取得開始 %s / %s", name, stamp, mod.SOURCE_URL)
        try:
            res = mod.scrape(session)
            normed = [c.normalize_event({**e, "facility_id": mod.FACILITY_ID,
                                         "source_url": e.get("source_url") or mod.SOURCE_URL}, stamp)
                      for e in res.events]
            bad = [(e, c.validate_event(e)) for e in normed]
            bad = [(e, p) for e, p in bad if p]
            for e, p in bad:
                log.error("[%s] 検証エラー %s: %s", name, e.get("title"), ", ".join(p))
            if bad:
                raise ValueError(f"データ検証エラー {len(bad)}件")
            if not normed and not res.confirmed_empty:
                raise ValueError("解析結果が0件（公式サイトで0件と確認できていないため失敗扱い）")
            for n in res.notes:
                log.info("[%s] 除外/要確認: %s", name, n)
            before = prev.get(mod.FACILITY_ID, 0)
            if before >= 5 and len(normed) <= before * DROP_WARN_RATIO:
                log.warning("[%s] 件数が大きく減少: %s件 → %s件", name, before, len(normed))
            events += normed
            rows.append((name, True, len(normed), res.pages, ""))
        except Exception as ex:  # 1施設でも失敗したら更新しない
            failed = True
            log.error("[%s] 失敗: %s", name, ex)
            rows.append((name, False, 0, 0, str(ex)))

    print("\n========== イベント情報取得結果 ==========\n")
    for name, ok, n, pages, err in rows:
        print(f"{name}：{'成功' if ok else '失敗'}  {n}件（{pages}ページ）" if ok else f"{name}：失敗  {err}")
    if failed:
        print("\n一部の施設で取得に失敗したため、events.json は更新しません（前回のデータを保持）。")
        return 1

    merged, dup = c.dedupe(events)
    kept = c.sort_events(c.drop_ended(merged, today))
    doc = c.build_document(old, kept)
    problems = c.validate_document(doc)
    print(f"\n取得合計：{len(events)}件\n重複排除：{dup}件\n期間終了で除外：{len(merged) - len(kept)}件\n最終登録件数：{len(kept)}件")
    if problems:
        print("JSON検証：失敗\n" + "\n".join(problems[:10]))
        return 1
    print("JSON検証：成功")
    if dry_run:
        print("ドライランのため events.json は変更しません。")
        for e in kept[:5]:
            print(" 例:", e["facility_id"], e["start_date"], e["title"])
    else:
        c.atomic_write_json(path, doc)
        print("更新処理：成功")
    print("==========================================")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--path", default="events.json")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(a.path, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
