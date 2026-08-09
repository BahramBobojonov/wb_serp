from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit


DEFAULT_SEARCH_URL = "https://www.wildberries.ru/__internal/u-search/exactmatch/ru/common/v18/search"


@dataclass(frozen=True)
class CurlTemplate:
    url: str
    headers: dict[str, str]
    cookies: dict[str, str]


def parse_curl_template(path: Path) -> CurlTemplate:
    text = path.read_text(encoding="utf-8-sig")
    url_match = re.search(r"curl(?:\.exe)?\s+[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    if not url_match:
        raise ValueError("curl URL not found")
    headers: dict[str, str] = {}
    for match in re.finditer(r"(?:-H|--header)\s+[\"']([^\"']+)[\"']", text, re.IGNORECASE):
        raw = match.group(1)
        if ":" in raw:
            name, value = raw.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    cookie_match = re.search(r"(?:-b|--cookie)\s+[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    cookie_text = cookie_match.group(1) if cookie_match else headers.pop("cookie", "")
    cookies: dict[str, str] = {}
    for item in cookie_text.split(";"):
        if "=" in item:
            name, value = item.split("=", 1)
            cookies[name.strip()] = value.strip()
    headers.pop("accept-encoding", None)
    if not cookies:
        raise ValueError("curl cookies not found")
    return CurlTemplate(url=url_match.group(1), headers=headers, cookies=cookies)


def build_search_url(template_url: str, query: str, page: int, dest: str) -> str:
    parts = urlsplit(template_url)
    if "/__internal/u-search/" not in parts.path:
        parts = urlsplit(DEFAULT_SEARCH_URL)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    defaults = {
        "ab_testing": "false",
        "appType": "64",
        "autoselectFilters": "false",
        "curr": "rub",
        "hide_vflags": "4294967296",
        "inheritFilters": "false",
        "lang": "ru",
        "locale": "ru",
        "resultset": "catalog",
        "scale": "4",
        "sort": "popular",
        "spp": "30",
        "suppressSpellcheck": "false",
    }
    for key, value in defaults.items():
        params.setdefault(key, value)
    params.update(query=query, page=str(page), dest=dest, resultset="catalog")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


class CurlClient:
    def __init__(self, template: CurlTemplate):
        self.template = template
        self.binary = shutil.which("curl.exe") or shutil.which("curl")
        if not self.binary:
            raise RuntimeError("curl binary not found")

    def fetch(self, query: str, page: int, dest: str) -> tuple[int, dict | None, str]:
        url = build_search_url(self.template.url, query, page, dest)
        headers = dict(self.template.headers)
        headers.setdefault("accept", "*/*")
        headers.setdefault("accept-language", "ru-RU,ru;q=0.9,en;q=0.7")
        headers.setdefault("x-requested-with", "XMLHttpRequest")
        headers.setdefault("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36")
        headers["referer"] = f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote_plus(query)}"
        user_id = self.template.cookies.get("_wbauid") or str(random.randint(10**17, 10**18 - 1))
        headers["x-queryid"] = f"qid{user_id}{time.strftime('%Y%m%d%H%M%S')}"
        command = [
            self.binary,
            "-4",
            "-L",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "20",
            "--max-time",
            "70",
            "--write-out",
            "\n__HTTP_STATUS__:%{http_code}",
            url,
            "-b",
            "; ".join(f"{key}={value}" for key, value in self.template.cookies.items()),
        ]
        for name, value in headers.items():
            if name not in {"cookie", "accept-encoding", "content-length"}:
                command.extend(["-H", f"{name}: {value}"])
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=100)
        marker = "\n__HTTP_STATUS__:"
        if marker not in result.stdout:
            return 0, None, (result.stderr or result.stdout)[:2000]
        body, status_text = result.stdout.rsplit(marker, 1)
        try:
            status = int(status_text.strip())
        except ValueError:
            status = 0
        try:
            data = json.loads(body) if body.lstrip().startswith(("{", "[")) else None
        except json.JSONDecodeError:
            data = None
        return status, data if isinstance(data, dict) else None, body[:2000]
