#!/usr/bin/env python3
"""Run the development questions with the LLM planner (layer 3) on (plan step P3.6).

The sealed holdout is excluded exactly as scripts/run_question_coverage.py excludes
it (scripts.sample_holdout.load_ids); no sealed question is asked or printed. Only
questions that resolve_query and the template planner refuse, and that pass the
layer-3 gate, reach the LLM. Replies are cached in data/processed/llm_cache/, so a
rerun gives the same replies and costs no request.

Fresh calls are paced under a tokens-per-minute budget (Groq's free plan allows
8,000 tokens per minute for openai/gpt-oss-120b). A failed call is retried once
after a pause; if it fails again the run stops, writes what it has, and can be
resumed by running the same command (cached replies are reused).

Outputs (no question text in tracked files):
- data/manifests/question_coverage_layer3.csv   one row per development question asked
- data/manifests/layer3_run_summary.json        counts, tokens, latency, model, prompt hash
- data/manifests/silver_v2_quality_layer3.json  (with --silver) silver v2 with layer 3 on
- data/processed/layer3_run/details.jsonl       (gitignored) replies, plans and checks to read

Usage:
    python scripts/run_layer3_coverage.py --dry-run     # gate only, no LLM call
    python scripts/run_layer3_coverage.py --limit 3     # stop after 3 fresh LLM calls
    python scripts/run_layer3_coverage.py --silver      # all development questions, then silver v2
"""

import argparse
from collections import Counter, deque
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Deque, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.evaluate_silver import evaluate as evaluate_silver
from scripts.sample_holdout import load_ids
from src.application.models import FinRAGResponse, ResponseStatus
from src.application.service import FinRAGApplication
from src.financial.program.llm_planner import DEFAULT_PLANNER_MAX_TOKENS, SYSTEM_PROMPT, LLMPlanner
from src.nlp.llm import (
    LLMConfigurationError,
    LLMResponse,
    LLMUnavailableError,
    OpenAICompatibleProvider,
    build_payload,
)

QUESTIONS_PATH = REPO_ROOT / "data" / "external" / "ViFinQA" / "questions" / "questions.jsonl"
SILVER_PATH = REPO_ROOT / "data" / "processed" / "gold_drafts" / "silver_v2.jsonl"
MANIFESTS = REPO_ROOT / "data" / "manifests"
DETAILS_PATH = REPO_ROOT / "data" / "processed" / "layer3_run" / "details.jsonl"
DEFAULT_TPM_BUDGET = 7000  # under Groq's 8,000 tokens per minute, with a margin
RETRY_PAUSE_S = 65.0


class PacedProvider:
    """Keep fresh calls under a tokens-per-minute budget; cached replies pass straight through."""

    def __init__(self, inner: OpenAICompatibleProvider, tokens_per_minute: int, first_estimate: int) -> None:
        self.inner = inner
        self.model = inner.model
        self.budget = tokens_per_minute
        self.estimate = first_estimate
        self.window: Deque[Tuple[float, int]] = deque()
        self.fresh_calls = 0
        self.waited_s = 0.0

    def is_cached(self, messages, temperature: float, max_tokens: int) -> bool:
        payload = build_payload(self.inner.model, messages, temperature, max_tokens)
        return self.inner.cache is not None and self.inner.cache.get(payload) is not None

    def complete(self, messages, *, temperature: float, max_tokens: int) -> LLMResponse:
        if self.is_cached(messages, temperature, max_tokens):
            return self.inner.complete(messages, temperature=temperature, max_tokens=max_tokens)
        self._wait_for_budget()
        self.fresh_calls += 1
        try:
            response = self.inner.complete(messages, temperature=temperature, max_tokens=max_tokens)
        except Exception:
            self.window.append((time.monotonic(), self.estimate))
            raise
        used = (response.prompt_tokens or 0) + (response.completion_tokens or 0) or self.estimate
        self.window.append((time.monotonic(), used))
        self.estimate = max(int(statistics.mean(tokens for _, tokens in self.window)), used // 2, 1)
        return response

    def _wait_for_budget(self) -> None:
        while True:
            now = time.monotonic()
            while self.window and now - self.window[0][0] >= 60.0:
                self.window.popleft()
            if sum(tokens for _, tokens in self.window) + self.estimate <= self.budget or not self.window:
                return
            pause = 60.0 - (now - self.window[0][0]) + 0.5
            self.waited_s += pause
            time.sleep(pause)


class DryRunProvider:
    """Answers nothing: every call is recorded and reported as unavailable, so no request is sent."""

    model = "dry-run"

    def __init__(self) -> None:
        self.calls: List[int] = []

    def complete(self, messages, *, temperature: float, max_tokens: int) -> LLMResponse:
        self.calls.append(sum(len(message["content"]) for message in messages))
        raise LLMUnavailableError("dry run: no request sent")


def answer_layer(response: FinRAGResponse) -> str:
    """Which path answered: resolution (base), template_lookup (layer 1), template_program (layer 2), llm (layer 3)."""
    if response.status not in (ResponseStatus.SUCCESS, ResponseStatus.WARNING):
        return ""
    planner = response.planner
    if planner is None:
        return "resolution"
    if planner.layer == "llm":
        return "llm"
    if response.trace is not None and len(response.trace.steps) == 1:
        return "template_lookup"
    return "template_program"


def row_for(question_id: int, response: FinRAGResponse) -> Dict[str, Any]:
    planner = response.planner
    llm_called = planner is not None and planner.layer == "llm" and planner.outcome != "not_attempted"
    return {
        "question_id": question_id,
        "ticker": response.ticker or "",
        "year_or_period": str(response.years) if response.years else (str(response.fiscal_year) if response.fiscal_year else ""),
        "resolved_metric": response.calculation.metric if response.calculation else "",
        "application_status": response.status.value,
        "error_category": response.error_category.value if response.error_category else "",
        "answer_layer": answer_layer(response),
        "planner_layer": planner.layer if planner else "",
        "planner_outcome": planner.outcome if planner else "",
        # Gate codes are fixed strings; model text never goes into this tracked file.
        "gate_reason": planner.reason if planner and planner.outcome == "not_attempted" else "",
        "llm_error_type": (planner.error_type or "") if planner else "",
        "llm_called": llm_called,
        "llm_cached": bool(planner.cached) if llm_called and planner.cached is not None else "",
        "prompt_tokens": planner.prompt_tokens if llm_called and planner.prompt_tokens is not None else "",
        "completion_tokens": planner.completion_tokens if llm_called and planner.completion_tokens is not None else "",
        "llm_latency_ms": round(planner.latency_ms, 1) if llm_called and planner.latency_ms is not None else "",
        "has_usable_evidence": bool(response.evidence),
        "evidence_count": len(response.evidence),
        "latency_ms": response.latency_ms,
    }


def detail_for(source: str, question_id: Any, response: FinRAGResponse) -> Dict[str, Any]:
    planner = response.planner
    trace = planner.model_dump() if planner else None
    if trace:
        trace["messages"] = [m for m in trace["messages"] if m["role"] != "system"]  # same system prompt everywhere
    return {
        "source": source,
        "id": question_id,
        "status": response.status.value,
        "error_category": response.error_category.value if response.error_category else None,
        "value": response.calculation.value if response.calculation else None,
        "unit": response.calculation.unit if response.calculation else None,
        "answer_label": response.calculation.answer_label if response.calculation else None,
        "metric": response.calculation.metric if response.calculation else None,
        "verification": response.verification.status if response.verification else None,
        "failed_checks": [c.name for c in response.verification.checks if c.status == "FAIL"] if response.verification else [],
        "warnings": response.verification.warnings if response.verification else [],
        "evidence": [
            {"fact_id": e.fact_id, "ticker": e.ticker, "year": e.fiscal_year, "line_code": e.line_code,
             "label": e.original_label, "value": e.value, "unit": e.unit, "unit_scale": e.unit_scale,
             "page": e.page, "source_path": e.source_path}
            for e in response.evidence
        ],
        "planner": trace,
    }


def ask_with_retry(app: FinRAGApplication, question: str) -> Tuple[FinRAGResponse, Optional[str]]:
    """Ask once; if the LLM call failed for a transport reason, pause and ask again once.

    Returns the response and, when the second attempt also failed, why the run must stop.
    A reply the model cut short (LLMResponseFormatError) is an answer about the model, not
    the network, so it is kept and the run continues.
    """
    response = app.ask(question)
    planner = response.planner
    if not (planner and planner.outcome == "unavailable"):
        return response, None
    if planner.error_type == "LLMConfigurationError":
        return response, f"configuration: {planner.reason}"
    if planner.error_type == "LLMResponseFormatError":
        return response, None
    time.sleep(RETRY_PAUSE_S)
    response = app.ask(question)
    planner = response.planner
    if planner and planner.outcome == "unavailable" and planner.error_type != "LLMResponseFormatError":
        return response, f"{planner.error_type}: {planner.reason}"
    return response, None


def describe(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "median": round(statistics.median(ordered), 1),
        "p90": round(ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))], 1),
        "max": round(ordered[-1], 1),
        "total": round(sum(ordered), 1),
    }


def git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout.strip()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="apply the gate only; send no request")
    parser.add_argument("--limit", type=int, default=None, help="stop after this many fresh LLM calls")
    parser.add_argument("--silver", action="store_true", help="also score silver v2 with layer 3 on")
    parser.add_argument("--tpm", type=int, default=DEFAULT_TPM_BUDGET, help="tokens-per-minute budget for fresh calls")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_PLANNER_MAX_TOKENS)
    args = parser.parse_args(argv)

    questions = [json.loads(line) for line in QUESTIONS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    sealed = load_ids()
    development = [item for item in questions if int(item["id"]) not in sealed]
    print(f"{len(development)} development questions ({len(sealed)} sealed questions excluded)")

    if args.dry_run:
        provider: Any = DryRunProvider()
        inner = None
    else:
        try:
            inner = OpenAICompatibleProvider.from_env()
        except LLMConfigurationError as error:
            print(f"LLM settings are not usable: {error}")
            return 2
        provider = PacedProvider(inner, args.tpm, first_estimate=4000)
    planner = LLMPlanner(provider, max_tokens=args.max_tokens)
    app = FinRAGApplication(llm_planner=planner)

    rows: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []
    stopped: Optional[str] = None
    started = time.perf_counter()
    for item in development:
        question_id = int(item["id"])
        if args.limit is not None and not args.dry_run and provider.fresh_calls >= args.limit:
            stopped = f"--limit {args.limit} fresh calls reached"
            break
        if args.dry_run:
            response, stop = app.ask(item["question"]), None
        else:
            response, stop = ask_with_retry(app, item["question"])
        rows.append(row_for(question_id, response))
        if response.planner is not None and response.planner.layer == "llm":
            details.append(detail_for("dev", question_id, response))
            row = rows[-1]
            if row["llm_called"]:
                print(f"  Q{question_id}: {row['planner_outcome']} -> {row['application_status']}"
                      f" (cached={row['llm_cached']}, tokens={row['prompt_tokens']}+{row['completion_tokens']})", flush=True)
        if stop:
            stopped = f"question {question_id}: {stop}"
            break
    elapsed_s = round(time.perf_counter() - started, 1)

    silver_manifest = None
    if args.silver and not args.dry_run and stopped is None:
        cases = [json.loads(line) for line in SILVER_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        for case in cases:  # fill the cache with the same retry rule, so scoring sees no transient failure
            response, stop = ask_with_retry(app, case["question"])
            if response.planner is not None and response.planner.layer == "llm":
                details.append(detail_for("silver", case["case_id"], response))
            if stop:
                stopped = f"silver {case['case_id']}: {stop}"
                break
        if stopped is None:
            silver_manifest = evaluate_silver(cases, app)
            silver_manifest["configuration"] = "layer 3 on (LLM planner)"
            silver_manifest["model"] = inner.model if inner else None
            silver_manifest["system_prompt_sha256"] = planner.system_prompt_sha256

    layer_counts = Counter(row["answer_layer"] or "refused" for row in rows)
    llm_rows = [row for row in rows if row["llm_called"]]
    fresh = [row for row in llm_rows if row["llm_cached"] is False]
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "configuration": "dry run (no LLM request)" if args.dry_run else "layer 3 on",
        "provider": inner.provider if inner else None,
        "model": inner.model if inner else None,
        "temperature": planner.temperature,
        "max_tokens": planner.max_tokens,
        "system_prompt_sha256": planner.system_prompt_sha256,
        "system_prompt_chars": len(SYSTEM_PROMPT),
        "development_questions": len(development),
        "sealed_excluded": len(sealed),
        "processed": len(rows),
        "stopped": stopped,
        "elapsed_s": elapsed_s,
        "status_counts": dict(Counter(row["application_status"] for row in rows)),
        "answered_by_layer": dict(layer_counts),
        "gate_reasons": dict(Counter(row["gate_reason"] for row in rows if row["gate_reason"])),
        "llm_outcomes": dict(Counter(row["planner_outcome"] for row in llm_rows)),
        "llm_status_after_checks": dict(Counter(row["application_status"] for row in llm_rows)),
        "llm_error_types": dict(Counter(row["llm_error_type"] for row in llm_rows if row["llm_error_type"])),
        "llm_calls": len(llm_rows),
        "llm_fresh_calls": len(fresh),
        "llm_cached_calls": sum(1 for row in llm_rows if row["llm_cached"] is True),
        "tokens_fresh": {
            "prompt": sum(int(row["prompt_tokens"] or 0) for row in fresh),
            "completion": sum(int(row["completion_tokens"] or 0) for row in fresh),
        },
        "tokens_all_calls": {
            "prompt": sum(int(row["prompt_tokens"] or 0) for row in llm_rows),
            "completion": sum(int(row["completion_tokens"] or 0) for row in llm_rows),
        },
        "llm_latency_ms_fresh": describe([float(row["llm_latency_ms"]) for row in fresh if row["llm_latency_ms"] != ""]),
        "answer_latency_ms_layer3": describe([row["latency_ms"] for row in rows if row["answer_layer"] == "llm"]),
        "pacing": None if args.dry_run else {
            "tokens_per_minute_budget": args.tpm,
            "waited_s": round(provider.waited_s, 1),
            "http_requests": inner.http_requests,
            "cache_hits": inner.cache_hits,
        },
        "dry_run_prompt_chars": describe([float(c) for c in provider.calls]) if args.dry_run else None,
    }

    MANIFESTS.mkdir(parents=True, exist_ok=True)
    suffix = "_dry_run" if args.dry_run else ""
    with open(MANIFESTS / f"question_coverage_layer3{suffix}.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["question_id"])
        writer.writeheader()
        writer.writerows(rows)
    (MANIFESTS / f"layer3_run_summary{suffix}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if silver_manifest is not None:
        (MANIFESTS / "silver_v2_quality_layer3.json").write_text(
            json.dumps(silver_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(silver_manifest["overall"]))
    DETAILS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DETAILS_PATH.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in details) + "\n", encoding="utf-8")

    print(json.dumps({k: summary[k] for k in (
        "processed", "stopped", "status_counts", "answered_by_layer", "gate_reasons", "llm_outcomes",
        "llm_status_after_checks", "llm_calls", "llm_fresh_calls", "tokens_fresh", "llm_latency_ms_fresh",
    )}, ensure_ascii=False, indent=1))
    if stopped:
        print(f"Stopped: {stopped}. Run the same command again to resume; cached replies are reused.")
    return 1 if stopped and not stopped.startswith("--limit") else 0


if __name__ == "__main__":
    sys.exit(main())
