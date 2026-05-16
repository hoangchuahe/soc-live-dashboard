"""
Fetches real CVE data from the NVD (National Vulnerability Database) public API.
No API key required. Results cached for 1 hour to respect rate limits.
https://nvd.nist.gov/developers/vulnerabilities
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

_cache: list[dict] = []
_fetched_at: datetime | None = None
_TTL = timedelta(hours=1)


async def fetch_recent_cves(limit: int = 15) -> list[dict]:
    global _cache, _fetched_at

    now = datetime.now(UTC)
    if _fetched_at and (now - _fetched_at) < _TTL and _cache:
        return _cache[:limit]

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                "https://services.nvd.nist.gov/rest/json/cves/2.0",
                params={"resultsPerPage": limit, "startIndex": 0},
                headers={"User-Agent": "SOC-Dashboard/1.0 (portfolio project)"},
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        parsed: list[dict] = []
        for item in data.get("vulnerabilities", []):
            cve = item.get("cve", {})

            # Extract best available CVSS score
            metrics = cve.get("metrics", {})
            cvss_score: float | None = None
            cvss_vector: str | None = None
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if key in metrics:
                    d = metrics[key][0]["cvssData"]
                    cvss_score = d.get("baseScore")
                    cvss_vector = d.get("vectorString")
                    break

            # English description
            descriptions = cve.get("descriptions", [])
            desc = next((d["value"] for d in descriptions if d["lang"] == "en"), "No description available.")

            parsed.append({
                "id": cve["id"],
                "description": desc[:300],
                "cvss": cvss_score,
                "cvss_vector": cvss_vector,
                "published": cve.get("published", ""),
                "severity": _cvss_to_severity(cvss_score),
            })

        _cache = parsed
        _fetched_at = now
        return parsed

    except Exception:
        # Fall back to cached data; return empty list only on first call
        return _cache[:limit]


def _cvss_to_severity(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"
