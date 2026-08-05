"""Transkribus TrpServer REST client (read-only subset).

Vendored from YiDraCor (Dybbuk repo). Auth: password grant -> JSESSIONID cookie.
Only the read endpoints needed for QA evaluation are included here; push paths
were intentionally omitted.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests

DEFAULT_BASE = "https://transkribus.eu/TrpServer/rest"


@dataclass
class TrpClient:
    user: str
    password: str
    base: str = DEFAULT_BASE
    session: requests.Session = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    @classmethod
    def from_env(cls, base: Optional[str] = None) -> "TrpClient":
        try:
            user = os.environ["TRANSKRIBUS_USER"]
            pw = os.environ["TRANSKRIBUS_PASS"]
        except KeyError as e:
            raise SystemExit(f"Missing env var {e}. Set TRANSKRIBUS_USER and TRANSKRIBUS_PASS.")
        c = cls(user=user, password=pw, base=base or DEFAULT_BASE)
        c.login()
        return c

    def login(self) -> None:
        resp = self.session.post(
            f"{self.base}/auth/login",
            data={"user": self.user, "pw": self.password},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Login failed ({resp.status_code}): {resp.text[:200]}")

    def list_collections(self) -> list[dict]:
        r = self.session.get(f"{self.base}/collections/list", timeout=30)
        r.raise_for_status()
        return r.json()

    def list_docs(self, col_id: int) -> list[dict]:
        r = self.session.get(f"{self.base}/collections/{col_id}/list", timeout=60)
        r.raise_for_status()
        return r.json()

    def fulldoc(self, col_id: int, doc_id: int) -> dict:
        r = self.session.get(
            f"{self.base}/collections/{col_id}/{doc_id}/fulldoc", timeout=120
        )
        r.raise_for_status()
        return r.json()

    def fetch_transcript(self, url: str) -> str:
        r = self.session.get(url, timeout=60)
        r.raise_for_status()
        return r.text

    def fetch_image(self, url: str) -> bytes:
        r = self.session.get(url, timeout=120)
        r.raise_for_status()
        return r.content
