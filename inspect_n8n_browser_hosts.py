from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sqlite3
from urllib.parse import urlparse


HISTORY_FILES = (
    Path(r"C:\Users\1SKY.IR\AppData\Local\Google\Chrome\User Data\Default\History"),
    Path(r"C:\Users\1SKY.IR\AppData\Local\Google\Chrome\User Data\Profile 1\History"),
    Path(r"C:\Users\1SKY.IR\AppData\Local\Microsoft\Edge\User Data\Default\History"),
)
EXCLUDED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "n8n.io",
    "docs.n8n.io",
    "community.n8n.io",
    "github.com",
    "www.google.com",
}


def main() -> None:
    latest_by_host: dict[str, int] = defaultdict(int)
    for history_path in HISTORY_FILES:
        if not history_path.exists():
            continue
        uri = history_path.as_uri() + "?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True)
            rows = connection.execute(
                "SELECT url, title, last_visit_time FROM urls "
                "WHERE lower(title) LIKE '%n8n%' "
                "OR lower(url) LIKE '%n8n%' "
                "OR url LIKE '%:5678/%'"
            ).fetchall()
        except sqlite3.Error:
            continue
        finally:
            if "connection" in locals():
                connection.close()
                del connection
        for url, title, last_visit_time in rows:
            parsed = urlparse(url)
            hostname = (parsed.hostname or "").lower()
            if (
                parsed.scheme == "https"
                and hostname
                and hostname not in EXCLUDED_HOSTS
                and ("n8n" in (title or "").lower() or "n8n" in url.lower())
            ):
                latest_by_host[hostname] = max(latest_by_host[hostname], int(last_visit_time or 0))

    for hostname, _ in sorted(latest_by_host.items(), key=lambda item: item[1], reverse=True):
        print(f"candidate_n8n_host={hostname}")


if __name__ == "__main__":
    main()
