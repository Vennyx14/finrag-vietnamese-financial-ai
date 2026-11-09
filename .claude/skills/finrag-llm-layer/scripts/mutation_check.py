"""Mutation check for the LLM provider layer (plan step P2).

Applies one deliberate break at a time to src/nlp/llm.py or scripts/check_llm_key.py
(an error mapping, a key redaction, the cache, the mock guard, the smoke check), runs
the LLM tests, and reports whether at least one test failed ("KILLED"). A mutation
that SURVIVES means no test notices that break: add a test before relying on that
code. This is how the tests check the code independently of whoever reviews it.

Usage (from a worktree under .claude/worktrees/, never the main checkout):
    python .claude/skills/finrag-llm-layer/scripts/mutation_check.py              # all groups
    python .claude/skills/finrag-llm-layer/scripts/mutation_check.py core cache   # some groups

Groups: core (error mappings E.., key leaks K..), cache (C..), mock (M..), smoke (S..).
Each source file is restored byte for byte after every mutation; the files must have
no uncommitted changes, so `git checkout -- <file>` can recover them if the run is
killed. Cache files a mutation leaves in data/processed/llm_cache/ are removed.
A row "SNIPPET COUNTS" means the code changed and that mutation needs updating.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LLM = "src/nlp/llm.py"
SCRIPT = "scripts/check_llm_key.py"
CACHE_DIR = ROOT / "data" / "processed" / "llm_cache"
TESTS = [
    "tests/test_llm_provider.py",
    "tests/test_llm_cache.py",
    "tests/test_llm_mock.py",
    "tests/test_check_llm_key.py",
    "tests/test_llm_env_file.py",
]

GROUPS = {
    "core": [
        # --- error mappings ---
        ("E01", "429 not mapped to LLMRateLimitError", LLM,
         "if failure.status in (402, 429):", "if failure.status in (402,):"),
        ("E02", "429 not retried", LLM,
         "if not (failure.status == 429 or 500 <= failure.status <= 599):",
         "if not (500 <= failure.status <= 599):"),
        ("E03", "Retry-After ignored (always exponential backoff)", LLM,
         "        if failure.retry_after is not None:\n            return failure.retry_after if",
         "        if False:\n            return failure.retry_after if"),
        ("E04", "Retry-After beyond max wait is slept instead of failing at once", LLM,
         "return failure.retry_after if failure.retry_after <= self.max_wait_s else None",
         "return failure.retry_after"),
        ("E05", "5xx (502-599) not retried", LLM,
         "failure.status == 429 or 500 <= failure.status <= 599", "failure.status == 429 or 500 <= failure.status <= 501"),
        ("E06", "5xx / other 4xx mapped to the wrong class", LLM,
         "        return LLMUnavailableError(\n            f\"{self.provider}: HTTP {failure.status}{hint}{detail}\"",
         "        return LLMResponseFormatError(\n            f\"{self.provider}: HTTP {failure.status}{hint}{detail}\""),
        ("E07", "retries not bounded to max_retries", LLM,
         "attempts = self.max_retries + 1", "attempts = self.max_retries + 2"),
        ("E08", "timeout/connection errors mapped to the wrong class", LLM,
         "raise LLMUnavailableError(self._network_message(error), provider=self.provider) from None",
         "raise LLMResponseFormatError(self._network_message(error), provider=self.provider) from None"),
        ("E09", "timeout/connection clause removed (raw OSError escapes)", LLM,
         "except (OSError, http.client.HTTPException) as error:", "except (http.client.HTTPException,) as error:"),
        ("E10", "timeout not recognised as a timeout", LLM,
         "if isinstance(reason, TimeoutError):", "if False:"),
        ("E11", "403 retried", LLM,
         "if not (failure.status == 429 or", "if not (failure.status in (403, 429) or"),
        ("E12", "403 mapped to LLMRateLimitError", LLM,
         "if failure.status in (402, 429):", "if failure.status in (402, 403, 429):"),
        ("E13", "HTTPError clause removed (statuses fall into the network clause)", LLM,
         "except urllib.error.HTTPError as error:", "except ZeroDivisionError as error:"),
        ("E14", "malformed JSON not mapped (raw JSONDecodeError escapes)", LLM,
         "            return json.loads(raw.decode(\"utf-8\"))\n        except ValueError:",
         "            return json.loads(raw.decode(\"utf-8\"))\n        except KeyError:"),
        ("E15", "missing/empty choices not checked", LLM,
         "if not isinstance(choices, list) or not choices:", "if False:"),
        ("E16", "missing message not checked", LLM,
         "if not isinstance(message, dict):\n            raise malformed(\"first choice has no message\")",
         "if message is None:\n            raise malformed(\"first choice has no message\")"),
        ("E17", "null/blank content not checked", LLM,
         "if not isinstance(content, str) or not content.strip():", "if content is None:"),
        ("E18", "reasoning field used as the answer", LLM,
         "content = message.get(\"content\")", "content = message.get(\"reasoning\") or message.get(\"content\")"),
        ("E19", "finish_reason=length hint removed", LLM,
         "            if finish_reason == \"length\":\n", "            if False:\n"),
        ("E20", "402 not a quota error", LLM,
         "if failure.status in (402, 429):", "if failure.status in (429,):"),
        ("E21", "redirects followed (default handler)", LLM,
         "urllib.request.build_opener(_NoRedirectHandler())", "urllib.request.build_opener()"),
        ("E22", "missing provider variable gets a default instead of an error", LLM,
         "    if problems:\n        raise LLMConfigurationError(",
         "    if False:\n        raise LLMConfigurationError("),
        ("E23", "http base URL accepted", LLM,
         "if not base_url.startswith(\"https://\") or not _is_plain_token(base_url):",
         "if not _is_plain_token(base_url):"),
        # --- the key never leaks ---
        ("K01", "exact-key redaction removed", LLM,
         "        text = text.replace(secret, \"[REDACTED]\")", "        text = text"),
        ("K02", "key-like token redaction removed", LLM,
         "    text = _KEY_LIKE.sub(\"[REDACTED]\", text)", "    text = text"),
        ("K03", "HTTP error body not redacted", LLM,
         "return self._redact(raw.decode(\"utf-8\", \"replace\"))", "return raw.decode(\"utf-8\", \"replace\")"),
        ("K04", "network error text not redacted", LLM,
         "{self._redact(str(reason))}", "{str(reason)}"),
        ("K05", "rejected-header error quoted in the message", LLM,
         "        except ValueError:\n            # http.client quotes a rejected header value, which would be the key.\n"
         "            raise LLMUnavailableError(\n"
         "                f\"{self.provider}: the request could not be sent (invalid header or URL)\"",
         "        except ValueError as error:\n            # http.client quotes a rejected header value, which would be the key.\n"
         "            raise LLMUnavailableError(\n"
         "                f\"{self.provider}: the request could not be sent ({error})\""),
        ("K06", "rejected-header error chained (traceback shows it)", LLM,
         "f\"{self.provider}: the request could not be sent (invalid header or URL)\", provider=self.provider\n"
         "            ) from None",
         "f\"{self.provider}: the request could not be sent (invalid header or URL)\", provider=self.provider\n"
         "            )"),
        ("K07", "non-JSON body snippet not redacted", LLM,
         "snippet = self._redact(raw.decode(\"utf-8\", \"replace\"))", "snippet = raw.decode(\"utf-8\", \"replace\")"),
        ("K08", "error-object message not redacted", LLM,
         "detail = f\": {self._redact(message)}\"", "detail = f\": {message}\""),
        ("K09", "provider repr shows the key", LLM,
         "model={self.model!r}, base_url={self.base_url!r})\"",
         "model={self.model!r}, base_url={self.base_url!r}, key={self._api_key.get_secret_value()!r})\""),
        ("K10", "provider keeps a plain-text copy of the key", LLM,
         "        self._api_key = SecretStr(key)\n", "        self._api_key = SecretStr(key)\n        self.key_text = key\n"),
        ("K11", "settings keep the key as plain str", LLM, [
            ("    model: str\n    api_key: SecretStr\n", "    model: str\n    api_key: Any\n"),
            ("api_key=SecretStr(found[\"api_key\"])", "api_key=found[\"api_key\"]"),
        ]),
        ("K12", "configuration error quotes the bad key", LLM,
         "\"character, which cannot be sent in an HTTP header; paste the key again\"",
         "f\"character, which cannot be sent in an HTTP header; paste the key again ({api_key})\""),
        ("K13", "retry log line includes the key", LLM,
         "self.provider, failure.status, attempt, self.max_retries, wait,",
         "self.provider + self._api_key.get_secret_value(), failure.status, attempt, self.max_retries, wait,"),
    ],
    "cache": [
        ("C01", "body stored before it is checked (format errors cached)", LLM,
         "        fields = self._completion_fields(body)  # raises before anything is cached\n"
         "        latency_ms = _elapsed_ms(started)\n"
         "        if self.cache is not None:\n"
         "            self._store(payload, body, latency_ms)\n",
         "        latency_ms = _elapsed_ms(started)\n"
         "        if self.cache is not None:\n"
         "            self._store(payload, body, latency_ms)\n"
         "        fields = self._completion_fields(body)\n"),
        ("C02", "cache never consulted", LLM,
         "hit = self._cached_response(payload, started)", "hit = None"),
        ("C03", "hit not flagged cached=True", LLM,
         "            cached=True,\n", "            cached=False,\n"),
        ("C04", "key formula changed (ensure_ascii)", LLM,
         "text = json.dumps(payload, sort_keys=True, ensure_ascii=False)", "text = json.dumps(payload, sort_keys=True)"),
        ("C05", "stored request not compared (stale entry served)", LLM,
         "if not isinstance(entry, dict) or entry.get(\"request\") != payload:", "if not isinstance(entry, dict):"),
        ("C06", "unreadable entry raises instead of being a miss", LLM,
         "        except (OSError, ValueError):\n            logger.warning(\"LLM cache entry %s is unreadable",
         "        except (KeyError,):\n            logger.warning(\"LLM cache entry %s is unreadable"),
        ("C07", "failed cache write loses the answer", LLM,
         "        except OSError as error:\n            logger.warning(\"could not write",
         "        except KeyError as error:\n            logger.warning(\"could not write"),
        ("C08", "key written into the cache file", LLM,
         "self.cache.put(payload, body, provider=self.provider, latency_ms=latency_ms)",
         "self.cache.put(payload, body, provider=self.provider + self._api_key.get_secret_value(), latency_ms=latency_ms)"),
        ("C09", "cache hits not counted", LLM,
         "        self.cache_hits += 1\n", ""),
        ("C10", "default cache directory moved", LLM,
         "DEFAULT_CACHE_DIR = REPO_ROOT / \"data\" / \"processed\" / \"llm_cache\"",
         "DEFAULT_CACHE_DIR = REPO_ROOT / \"llm_cache\""),
        ("C11", "from_env does not cache by default", LLM,
         "cache_dir: Optional[Union[str, Path]] = DEFAULT_CACHE_DIR,", "cache_dir: Optional[Union[str, Path]] = None,"),
        ("C12", "hit reports the current provider instead of the source", LLM,
         "provider=source if isinstance(source, str) and source else self.provider,", "provider=self.provider,"),
    ],
    "mock": [
        ("M01", "mock can be created outside pytest", LLM,
         "        _require_pytest()\n        self.model = model\n", "        self.model = model\n"),
        ("M02", "mock answers outside pytest", LLM,
         "        _require_pytest()\n        payload = build_payload(self.model, messages, temperature, max_tokens)\n"
         "        self.calls.append(payload)",
         "        payload = build_payload(self.model, messages, temperature, max_tokens)\n"
         "        self.calls.append(payload)"),
        ("M03", "pytest check always passes", LLM,
         "if \"PYTEST_CURRENT_TEST\" not in os.environ:", "if False:"),
        ("M04", "mock skips request validation", LLM,
         "        payload = build_payload(self.model, messages, temperature, max_tokens)\n        self.calls.append(payload)",
         "        payload = {\"model\": self.model, \"messages\": messages, \"temperature\": temperature, "
         "\"max_tokens\": max_tokens}\n        self.calls.append(payload)"),
        ("M05", "scripted failure returned instead of raised", LLM,
         "        if isinstance(item, BaseException):\n            raise item\n", ""),
    ],
    "smoke": [
        ("S01", "smoke does not verify the cache hit", SCRIPT,
         "if first.cached or not second.cached or requests_for_second != 0:", "if False:"),
        ("S02", "smoke runs without a cache", SCRIPT,
         "provider = OpenAICompatibleProvider.from_env(env_path, cache_dir=cache_dir)",
         "provider = OpenAICompatibleProvider.from_env(env_path, cache_dir=None)"),
        ("S03", "key check prints the provider's error body unredacted", SCRIPT,
         "detail = redact(error.read().decode(\"utf-8\", \"replace\"), key)[:120]",
         "detail = error.read().decode(\"utf-8\", \"replace\")[:120]"),
        ("S04", "smoke uses the persistent default cache (a rerun would make no real call)", SCRIPT,
         "provider = OpenAICompatibleProvider.from_env(env_path, cache_dir=cache_dir)",
         "provider = OpenAICompatibleProvider.from_env(env_path)"),
    ],
}


def run_tests():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *[t for t in TESTS if (ROOT / t).exists()]],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    failed = [line.split(" ")[1] for line in proc.stdout.splitlines() if line.startswith(("FAILED ", "ERROR "))]
    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr.strip()[-200:]
    return proc.returncode, failed, summary


def check_preconditions(files):
    if ".claude/worktrees/" not in ROOT.as_posix() + "/":
        sys.exit(f"Refusing to run in {ROOT}: run it from a worktree under .claude/worktrees/ (AGENTS.md section 10).")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", *files], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        sys.exit(f"Commit or stash these files first, so a killed run can be undone with git checkout:\n{dirty}")


def main(groups):
    unknown = [group for group in groups if group not in GROUPS]
    if unknown:
        sys.exit(f"Unknown group(s) {unknown}; choose from {sorted(GROUPS)}")
    entries = [entry for group in groups for entry in GROUPS[group]]
    files = sorted({entry[2] for entry in entries})
    check_preconditions(files)
    cache_before = set(CACHE_DIR.iterdir()) if CACHE_DIR.exists() else None
    originals = {rel: (ROOT / rel).read_bytes() for rel in files}
    rows = []
    try:
        for entry in entries:
            mid, description, rel = entry[:3]
            edits = entry[3] if len(entry) == 4 else [(entry[3], entry[4])]
            source = originals[rel].decode("utf-8")
            counts = [source.count(old) for old, _ in edits]
            if counts != [1] * len(edits):
                rows.append((mid, description, f"SNIPPET COUNTS {counts}", [], ""))
                continue
            for old, new in edits:
                source = source.replace(old, new)
            (ROOT / rel).write_bytes(source.encode("utf-8"))
            try:
                code, failed, summary = run_tests()
            finally:
                (ROOT / rel).write_bytes(originals[rel])
            rows.append((mid, description, "KILLED" if code != 0 else "SURVIVED", failed, summary))
    finally:
        for rel, data in originals.items():
            (ROOT / rel).write_bytes(data)
        if CACHE_DIR.exists():  # entries written by a mutation that used the default cache
            for path in set(CACHE_DIR.iterdir()) - (cache_before or set()):
                path.unlink()
            if cache_before is None and not any(CACHE_DIR.iterdir()):
                CACHE_DIR.rmdir()
    for rel, data in originals.items():
        assert (ROOT / rel).read_bytes() == data, f"{rel} was not restored"
    for mid, description, verdict, failed, summary in rows:
        print(f"{mid} {verdict:9} {description}")
        print(f"     {summary}")
        for name in failed[:4]:
            print(f"     - {name}")
        if len(failed) > 4:
            print(f"     ... {len(failed) - 4} more")
    not_killed = [row[0] for row in rows if row[2] != "KILLED"]
    print(f"\n{len(rows)} mutations, {len(rows) - len(not_killed)} killed, not killed: {not_killed or 'none'}")
    return 1 if not_killed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or sorted(GROUPS)))
