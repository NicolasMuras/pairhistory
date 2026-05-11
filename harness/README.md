# Replay harness

A minimal script that loads a captured send-list JSON, sends it to LM Studio with a fresh seed, and prints the response. Built for the offline-replay methodology described in [the post][BLOG_POST_URL].

## What it does

- Loads a JSON file containing a complete chat-completions payload (`model`, `messages`, sampling params, etc.).
- POSTs to your local LM Studio endpoint at `http://localhost:1234/v1/chat/completions` (configurable via `--url`).
- Generates a random seed per run (client-side), or uses a fixed seed if `--seed` is given.
- Prints the seed, wall-clock latency, completion token count (when LM Studio returns it), character count, and the response text.
- In `--batch N` mode, runs N times with random seeds and prints aggregate min/max/mean/median for latency and tokens.

It does **no** evaluation, no string comparison, no heuristics. You read the responses and judge them. That's the methodology.

## Requirements

- Python 3.8 or newer
- LM Studio running locally with the OpenAI-compatible server enabled
- `colorama` (optional, for colored output) — `pip install -r requirements.txt`

## Usage

Single run with a random seed:

```bash
python replay.py ../send_lists/case1_first_turn.json
```

Single run with a fixed seed (deterministic, given the same prompt and model build):

```bash
python replay.py ../send_lists/case1_first_turn.json --seed 12345
```

Batch of 20 runs with random seeds (how the post's numbers were produced):

```bash
python replay.py ../send_lists/case1_first_turn.json --batch 20
```

Different LM Studio endpoint:

```bash
python replay.py ../send_lists/case1_first_turn.json --url http://192.168.1.50:1234/v1/chat/completions
```

## Determinism caveats

- Same prompt + same seed + same model build = identical output. This holds within a single LM Studio session.
- Changing any byte of the prompt invalidates seed-to-seed reproducibility. The post's comparisons are all statistical over N=20 random seeds per variant — never seed-matched across variants.
- Different model quantizations, different LM Studio versions, or different hardware may shift the numbers. The patterns should hold; the exact percentages won't.

## Why this shape

The replay harness exists because production debugging conflates two questions:

1. **Is the system producing the right prompt?**
2. **Is the model producing a good response under that prompt?**

When you debug live, both are tangled. Capture the send-list as JSON at the moment your system is about to call the LLM, replay it offline with the harness, and the two questions separate. The first becomes a question for your application logs. The second becomes a question for this script.

This is the single most useful methodological practice I picked up while iterating on the patterns.
