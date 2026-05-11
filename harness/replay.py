"""
replay.py — minimal LM Studio replay harness, with colored output and metrics.

Reads a send-list JSON file (containing model, params, and messages) and
calls the local LM Studio endpoint. Prints the seed, latency, token/char
count, and the response.

Usage:
    python replay.py <sendlist.json>                 # one run with random seed
    python replay.py <sendlist.json> --seed 12345    # one run with fixed seed
    python replay.py <sendlist.json> --batch 10      # 10 runs with random seeds

Notes:
- No string comparison. No heuristics. Just prints what came back.
- Seed is generated client-side and sent in the request body. LM Studio
  honors the `seed` field for deterministic sampling within the same prompt.
  Changing any byte of the prompt invalidates seed-to-seed reproducibility.
- The script does not modify the JSON; copy it and edit a copy if you
  want to iterate prompt variants.

Metrics printed per run:
- seed: the seed used.
- elapsed: wall-clock time of the HTTP call.
- tokens (when available): completion_tokens from the response usage block.
                           Falls back to char count if the field is missing.
- response: the model's text.

At the end of a batch of N>1, an aggregate summary is printed:
- min / max / mean / median latency.
- min / max / mean / median tokens (or chars).
"""

import argparse
import json
import random
import statistics
import sys
import time
import urllib.request
import urllib.error

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    COLOR = True
except ImportError:
    # Soft fallback so the script runs without colorama installed.
    class _NoColor:
        def __getattr__(self, name): return ""
    Fore = _NoColor()
    Style = _NoColor()
    COLOR = False


DEFAULT_URL = "http://localhost:1234/v1/chat/completions"


def call_lm_studio(payload: dict, url: str = DEFAULT_URL, timeout: int = 300) -> dict:
    """POST the payload to LM Studio and return the parsed JSON response."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection error: {e.reason}") from e


def extract_response_text(response: dict) -> str:
    """Extract the assistant message content from an OpenAI-compatible response."""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        return f"[could not extract content: {e}]\nFull response: {json.dumps(response, indent=2)}"


def extract_completion_tokens(response: dict):
    """
    Extract completion_tokens from the usage block. Returns None if absent.
    LM Studio includes a usage block in OpenAI-compatible mode; some setups
    or older versions may omit it.
    """
    try:
        return response.get("usage", {}).get("completion_tokens")
    except (AttributeError, TypeError):
        return None


class RunResult:
    __slots__ = ("seed", "elapsed_s", "text", "tokens", "chars", "error")

    def __init__(self, seed, elapsed_s, text, tokens, chars, error=None):
        self.seed = seed
        self.elapsed_s = elapsed_s
        self.text = text
        self.tokens = tokens
        self.chars = chars
        self.error = error


def run_once(base_payload: dict, seed: int, url: str) -> RunResult:
    """Run the request with the given seed. Returns a RunResult."""
    payload = dict(base_payload)
    payload["seed"] = seed

    start = time.perf_counter()
    try:
        response = call_lm_studio(payload, url=url)
        elapsed = time.perf_counter() - start
    except Exception as e:
        elapsed = time.perf_counter() - start
        return RunResult(seed, elapsed, "", None, 0, error=str(e))

    text = extract_response_text(response)
    tokens = extract_completion_tokens(response)
    chars = len(text) if isinstance(text, str) else 0
    return RunResult(seed, elapsed, text, tokens, chars)


def fmt_metric_line(result: RunResult) -> str:
    """One-line summary of seed/latency/tokens for a single run."""
    parts = [f"{Fore.CYAN}seed{Style.RESET_ALL}: {result.seed}"]
    parts.append(f"{Fore.CYAN}elapsed{Style.RESET_ALL}: {result.elapsed_s:.2f}s")
    if result.tokens is not None:
        parts.append(f"{Fore.CYAN}tokens{Style.RESET_ALL}: {result.tokens}")
    parts.append(f"{Fore.CYAN}chars{Style.RESET_ALL}: {result.chars}")
    return "  ".join(parts)


def print_run(result: RunResult, run_index: int = None, total: int = None):
    if run_index is not None and total is not None and total > 1:
        print(f"\n{Fore.YELLOW}=== Run {run_index}/{total} ==={Style.RESET_ALL}")

    print(fmt_metric_line(result))

    if result.error:
        print(f"{Fore.RED}error{Style.RESET_ALL}: {result.error}")
        return

    print(f"{Fore.GREEN}response{Style.RESET_ALL}: {result.text}")


def print_aggregate(results):
    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]

    print(f"\n{Fore.MAGENTA}=== Aggregate over {len(results)} runs ==={Style.RESET_ALL}")
    if failed:
        print(f"{Fore.RED}failed{Style.RESET_ALL}: {len(failed)}")
    if not successful:
        return

    latencies = [r.elapsed_s for r in successful]
    tokens_present = [r.tokens for r in successful if r.tokens is not None]
    chars = [r.chars for r in successful]

    def stats_block(label, values, unit=""):
        if not values:
            return
        print(
            f"{Fore.CYAN}{label}{Style.RESET_ALL}: "
            f"min={min(values):.2f}{unit} "
            f"max={max(values):.2f}{unit} "
            f"mean={statistics.mean(values):.2f}{unit} "
            f"median={statistics.median(values):.2f}{unit}"
        )

    stats_block("latency", latencies, "s")
    if tokens_present:
        stats_block("tokens", tokens_present)
        if len(tokens_present) < len(successful):
            print(
                f"  {Fore.YELLOW}note{Style.RESET_ALL}: "
                f"{len(successful) - len(tokens_present)} run(s) had no token count"
            )
    stats_block("chars", chars)


def main():
    parser = argparse.ArgumentParser(description="LM Studio replay harness with colored output and metrics.")
    parser.add_argument("sendlist", help="Path to JSON file with the request payload.")
    parser.add_argument("--seed", type=int, default=None,
                        help="Fixed seed. If omitted, a random seed is generated.")
    parser.add_argument("--batch", type=int, default=1,
                        help="Number of runs (each with its own random seed). Ignored if --seed is set.")
    parser.add_argument("--url", default=DEFAULT_URL,
                        help=f"LM Studio endpoint (default: {DEFAULT_URL})")
    args = parser.parse_args()

    try:
        with open(args.sendlist, "r", encoding="utf-8") as f:
            base_payload = json.load(f)
    except FileNotFoundError:
        print(f"{Fore.RED}error{Style.RESET_ALL}: file not found: {args.sendlist}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{Fore.RED}error{Style.RESET_ALL}: invalid JSON in {args.sendlist}: {e}", file=sys.stderr)
        sys.exit(1)

    if args.seed is not None:
        seeds = [args.seed]
    else:
        seeds = [random.randint(0, 2**31 - 1) for _ in range(args.batch)]

    if not COLOR:
        print("(colorama not installed; output will be uncolored. Install with: pip install colorama)")

    results = []
    total_start = time.perf_counter()
    for i, seed in enumerate(seeds, start=1):
        result = run_once(base_payload, seed, args.url)
        results.append(result)
        print_run(result, run_index=i, total=len(seeds))

    if len(seeds) > 1:
        total_elapsed = time.perf_counter() - total_start
        print_aggregate(results)
        print(f"{Fore.CYAN}total wall time{Style.RESET_ALL}: {total_elapsed:.2f}s")


if __name__ == "__main__":
    main()
