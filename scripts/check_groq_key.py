#!/usr/bin/env python3
"""Check GROQ_API_KEY from .env with one request. The key itself is never printed.

Usage:
    python scripts/check_groq_key.py
"""

import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
MODELS_URL = "https://api.groq.com/openai/v1/models"


def read_key(path: Path) -> str:
    """Return GROQ_API_KEY from a .env file, or an empty string."""
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, _, value = line.partition("=")
        if name.strip() == "GROQ_API_KEY":
            return value.strip().strip("\"'")
    return ""


def main() -> int:
    key = read_key(ENV_PATH)
    if not key:
        print(f"Không thấy GROQ_API_KEY trong {ENV_PATH}")
        return 1
    request = urllib.request.Request(
        MODELS_URL,
        headers={"Authorization": f"Bearer {key}", "User-Agent": "finrag-key-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            models = sorted(item["id"] for item in json.load(response)["data"])
    except urllib.error.HTTPError as error:
        print(f"Groq từ chối khóa: HTTP {error.code}")
        return 1
    except urllib.error.URLError as error:
        print(f"Không kết nối được tới Groq: {error.reason}")
        return 1
    print(f"Khóa hợp lệ. Có {len(models)} model.")
    for model in models:
        print(f"  {model}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
