from __future__ import annotations

import base64
import json
from pathlib import Path
import urllib.parse
import urllib.request


CERT_PATH = Path(r"C:\Users\1SKY.IR\.cloudflared\cert.pem")
TUNNEL_ID = "00434205-702a-4477-b948-6f316cb45bf3"


def main() -> None:
    certificate = CERT_PATH.read_text(encoding="utf-8")
    encoded = "".join(
        line.strip()
        for line in certificate.splitlines()
        if line and not line.startswith("---")
    )
    credential = json.loads(base64.b64decode(encoded))
    target = f"{TUNNEL_ID}.cfargotunnel.com"
    query = urllib.parse.urlencode(
        {"type": "CNAME", "content": target, "per_page": 100}
    )
    url = (
        "https://api.cloudflare.com/client/v4/zones/"
        f"{credential['zoneID']}/dns_records?{query}"
    )
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {credential['apiToken']}"},
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler(
            {
                "http": "http://127.0.0.1:10808",
                "https": "http://127.0.0.1:10808",
            }
        )
    )
    with opener.open(request, timeout=15) as response:
        payload = json.load(response)
    if not payload.get("success"):
        raise RuntimeError("Cloudflare DNS metadata request failed")
    hostnames = sorted(
        record["name"]
        for record in payload.get("result", [])
        if str(record.get("content", "")).lower() == target.lower()
    )
    for hostname in hostnames:
        print(f"cloudflare_tunnel_hostname={hostname}")
    if not hostnames:
        print("cloudflare_tunnel_hostname=none")


if __name__ == "__main__":
    main()
