#!/usr/bin/env python3
"""Check the LLM API key in .env with one request. The key itself is never printed.

Supports CEREBRAS_API_KEY, OPENROUTER_API_KEY, and GROQ_API_KEY. Groq rejects
connections from some networks before it reads the key.

Usage:
    python scripts/check_llm_key.py
"""

import json
from pathlib import Path
import sys
from typing import Dict
import urllib.error
import urllib.request

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
CHECK_URLS = {
    "CEREBRAS_API_KEY": "https://api.cerebras.ai/v1/models",
    "OPENROUTER_API_KEY": "https://openrouter.ai/api/v1/key",
    "GROQ_API_KEY": "https://api.groq.com/openai/v1/models",
}


def read_env(path: Path) -> Dict[str, str]:
    """Return KEY=value pairs from a .env file."""
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, _, value = line.partition("=")
        if value.strip():
            values[name.strip()] = value.strip().strip("\"'")
    return values


def check(name: str, key: str) -> bool:
    request = urllib.request.Request(
        CHECK_URLS[name],
        headers={"Authorization": f"Bearer {key}", "User-Agent": "finrag-key-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:120]
        print(f"{name}: bị từ chối, HTTP {error.code}. {detail}")
        return False
    except urllib.error.URLError as error:
        print(f"{name}: không kết nối được ({error.reason}).")
        return False
    if name == "OPENROUTER_API_KEY":
        data = body.get("data", {})
        print(f"{name}: hợp lệ. Gói miễn phí: {data.get('is_free_tier')}. Đã dùng: {data.get('usage')}.")
    else:
        print(f"{name}: hợp lệ. Có {len(body.get('data', []))} model.")
    return True


def main() -> int:
    values = read_env(ENV_PATH)
    names = [name for name in CHECK_URLS if values.get(name)]
    if not names:
        print(f"Không thấy khóa nào ({', '.join(CHECK_URLS)}) trong {ENV_PATH}")
        return 1
    results = [check(name, values[name]) for name in names]
    return 0 if any(results) else 1


if __name__ == "__main__":
    sys.exit(main())
