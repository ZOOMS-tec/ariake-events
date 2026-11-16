import os

from scripts import common as c

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
c.FETCH_INTERVAL = 0  # テストではアクセス間隔を空けない


def fixture(name: str) -> str:
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code, self.content, self.headers, self.encoding = text, status, text.encode(), {}, "utf-8"


class FakeSession:
    """URL→HTML の辞書から返す。外部通信はしない。"""
    def __init__(self, pages):
        self.pages, self.requested = pages, []
        self.headers = {}

    def get(self, url, timeout=None):
        self.requested.append(url)
        if url not in self.pages:
            return Resp("not found", 404)
        return Resp(self.pages[url])
