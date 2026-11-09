#!/usr/bin/env python3
"""Check the LLM settings in .env with real requests. The key itself is never printed.

Without options: check every key that is set (CEREBRAS_API_KEY, OPENROUTER_API_KEY,
GROQ_API_KEY) with one request each. Groq rejects connections from some networks
before it reads the key.

With --smoke: send one tiny chat request through the provider that
FINRAG_LLM_PROVIDER selects (src/nlp/llm.py), then send the same request again to
show that the disk cache answers it without a second network call. The cache is a
temporary folder, so every smoke run makes exactly one real call and leaves nothing.

Usage:
    python scripts/check_llm_key.py
    python scripts/check_llm_key.py --smoke
"""

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import List, Optional
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.nlp.env_file import read_env_file  # noqa: E402
from src.nlp.llm import LLMError, OpenAICompatibleProvider, redact  # noqa: E402

ENV_PATH = REPO_ROOT / ".env"
CHECK_URLS = {
    "CEREBRAS_API_KEY": "https://api.cerebras.ai/v1/models",
    "OPENROUTER_API_KEY": "https://openrouter.ai/api/v1/key",
    "GROQ_API_KEY": "https://api.groq.com/openai/v1/models",
}
SMOKE_PROMPT = "Trả lời đúng một từ: OK"


def check(name: str, key: str) -> bool:
    request = urllib.request.Request(
        CHECK_URLS[name],
        headers={"Authorization": f"Bearer {key}", "User-Agent": "finrag-key-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        detail = redact(error.read().decode("utf-8", "replace"), key)[:120]
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


def check_keys(env_path: Path = ENV_PATH) -> int:
    values = read_env_file(env_path)
    names = [name for name in CHECK_URLS if values.get(name)]
    if not names:
        print(f"Không thấy khóa nào ({', '.join(CHECK_URLS)}) trong {env_path}")
        return 1
    results = [check(name, values[name]) for name in names]
    return 0 if any(results) else 1


def smoke(env_path: Path = ENV_PATH, temp_root: Optional[Path] = None) -> int:
    """One real chat call, then the same call again, which the cache must answer."""
    messages = [{"role": "user", "content": SMOKE_PROMPT}]
    with tempfile.TemporaryDirectory(prefix="finrag-llm-smoke-", dir=temp_root) as cache_dir:
        try:
            provider = OpenAICompatibleProvider.from_env(env_path, cache_dir=cache_dir)
            first = provider.complete(messages)
            requests_for_first = provider.http_requests
            second = provider.complete(messages)
        except LLMError as error:
            print(f"{error.user_message}: {error}")
            return 1
    requests_for_second = provider.http_requests - requests_for_first
    print(f"Nhà cung cấp: {provider.provider}, model: {first.model}")
    print(
        f"Lần 1: trả lời {first.text.strip()[:80]!r}, {first.latency_ms:.0f} ms, "
        f"{requests_for_first} yêu cầu HTTP, token vào {first.prompt_tokens}, token ra {first.completion_tokens}, "
        f"finish_reason {first.finish_reason}"
    )
    print(
        f"Lần 2 (cùng câu hỏi): trả lời {second.text.strip()[:80]!r}, cached={second.cached}, "
        f"{second.latency_ms:.1f} ms, {requests_for_second} yêu cầu HTTP"
    )
    if first.cached or not second.cached or requests_for_second != 0:
        print("Lỗi: lần gọi thứ hai không được trả lời từ bộ đệm.")
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check the LLM settings in .env; the key is never printed.")
    parser.add_argument(
        "--smoke", action="store_true", help="send one real chat request, then repeat it to test the cache"
    )
    args = parser.parse_args(argv)
    return smoke() if args.smoke else check_keys()


if __name__ == "__main__":
    sys.exit(main())
