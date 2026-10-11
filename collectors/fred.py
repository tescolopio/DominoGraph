"""Optional real adapter: FRED observations only, never arbitrary URLs."""

import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, build_opener

from collectors.base import Collected


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class FredCollector:
    def __init__(self, series_id: str):
        if not re.fullmatch(r"[A-Z0-9_]{1,80}", series_id):
            raise ValueError("invalid FRED series identifier")
        self.series_id = series_id

    def collect(self) -> Collected:
        key = os.environ.get("FRED_API_KEY")
        if not key:
            raise ValueError("FRED_API_KEY is required for optional FRED collection")
        base = "https://api.stlouisfed.org/fred/series/observations"
        url = base + "?" + urlencode({"series_id": self.series_id, "api_key": key,
                                      "file_type": "json"})
        try:
            with build_opener(NoRedirect()).open(url, timeout=15) as response:
                content = response.read(5_000_001)
                if len(content) > 5_000_000:
                    raise ValueError("FRED response exceeds size limit")
                text = content.decode("utf-8")
                if not isinstance(json.loads(text).get("observations"), list):
                    raise ValueError("FRED response has no observation array")
        except (HTTPError, URLError, TimeoutError):
            # Exceptions may include the credential-bearing request URL.
            raise ValueError("FRED collection failed; inspect configuration or retry") from None
        return Collected("https://fred.stlouisfed.org/series/" + self.series_id,
                         datetime.now(timezone.utc), text, "fred-urllib-v1")
