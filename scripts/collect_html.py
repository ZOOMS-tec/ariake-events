"""調査用：各施設の公式ページとrobots.txtを取得して html_samples/ に保存する（解析はしない）。"""
import os
import re
from urllib.parse import urlsplit

from scripts import common as c

URLS = [
    "https://www.bigsight.jp/visitor/event/",
    "https://www.shopping-sumitomo-rd.com/tokyo_garden_theater/schedule/",
    "https://ariake-arena.tokyo/event/",
    "https://ariake.shopping-sumitomo-rd.com/event/",
    "https://ariake-usp.com/event",
]
EXTRA = ["https://ariake-usp.com/sitemap.xml"]  # 追加調査用（サイトマップ）
OUT = "html_samples"


def slug(u):
    p = urlsplit(u)
    return re.sub(r"\W+", "_", p.netloc + p.path).strip("_")


def discover_usp(s, report):
    """有明アーバンスポーツパーク：イベント詳細ページがサイトマップ経由で取得できるか調べる。"""
    try:
        idx = c.fetch(s, "https://ariake-usp.com/sitemap.xml", retries=2).text
    except Exception as e:
        report.append(f"NG usp sitemap {e}")
        return
    for sm in [u for u in re.findall(r"<loc>([^<]+)</loc>", idx) if "ZXZlbnQ" in u]:  # base64「event/:slug」
        try:
            xml = c.fetch(s, sm, retries=2).text
            with open(os.path.join(OUT, "usp_event_sitemap.xml"), "w", encoding="utf-8") as f:
                f.write(xml)
            urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", xml) if "/event/" in u]
            report.append(f"OK usp event sitemap: {len(urls)} urls")
            for i, u in enumerate(urls[:3]):
                r = c.fetch(s, u, retries=2)
                with open(os.path.join(OUT, f"usp_event_detail_{i}.html"), "wb") as f:
                    f.write(r.content)
                report.append(f"OK {r.status_code} {len(r.content)}B {u}")
        except Exception as e:
            report.append(f"NG usp {e} {sm}")


def main():
    os.makedirs(OUT, exist_ok=True)
    s = c.make_session()
    robots = sorted({f"{urlsplit(u).scheme}://{urlsplit(u).netloc}/robots.txt" for u in URLS})
    report = []
    for u in URLS + robots + EXTRA:
        try:
            r = c.fetch(s, u, retries=2)
            name = slug(u) + (".txt" if u.endswith("robots.txt") else ".xml" if u.endswith(".xml") else ".html")
            with open(os.path.join(OUT, name), "wb") as f:
                f.write(r.content)
            h = r.text
            report.append(f"OK {r.status_code} {len(r.content)}B type={r.headers.get('content-type')} "
                          f"a={h.count('<a ')} script={h.count('<script')} {u}")
        except Exception as e:
            report.append(f"NG {e} {u}")
    discover_usp(s, report)
    text = "\n".join(report)
    print(text)
    with open(os.path.join(OUT, "_report.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
