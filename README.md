---
title: HR Operations Agent
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
short_description: Claude HR self-service agent, multi-tool orchestration
---

# HR Operations Agent

> *"I diagnosed this problem at work, proposed building it as an internal tool, and built the
> demo because the real version couldn't deploy due to compliance constraints."*

A Claude-native HR self-service agent that routes a question across four tools — process
docs, known-issue lookup, IT ownership, escalation paths — and synthesizes one cited answer.
The orchestration is ~90 lines of native Anthropic tool-use: no LangChain, no CrewAI. The
point of the project is not the agent. It is the **measurement around it** — routing
accuracy, retrieval quality, adversarial robustness, and per-query cost, each shipping a
number instead of an adjective.

| | |
|---|---|
| **Routing accuracy** | 100% on 82 scored golden queries |
| **Retrieval recall@3** | 0.97 process · 0.94 tickets (BGE-M3 hybrid) |
| **Adversarial success rate** | 0.0% across 50 probes (v1.0 full red-team) |
| **Cached prefix** | 1,785 tokens → 90% cheaper per read |

---

## Problem

HR teams at mid-size organizations keep critical operational knowledge in people's heads:
undocumented processes, known system workarounds, and unwritten escalation paths. When
someone leaves, that knowledge leaves with them. A new joiner who needs to know *"my Workday
access is broken — who do I even call?"* spends days chasing an answer that should take
minutes.

The instinctive fix is a chatbot over a wiki. That fails for HR ops specifically, because a
real question crosses domains: it is simultaneously a *known issue* (is there a workaround?),
an *ownership* question (whose system is this?), and an *escalation* question (what's the SLA,
who do I page?). A single semantic search returns the closest document; it does not
*reason across* the three. That reasoning is the job this agent does.

---

## Approach

A single-loop Claude agent decides which of four tools to call, in what order, then
synthesizes one response with source citations:

| Tool | What it answers | Retrieval |
|---|---|---|
| `search_process_docs` | "How do I…" — process & onboarding how-tos | BGE-M3 dense-primary |
| `lookup_known_issues` | "X is broken" — workarounds, fix status, ticket refs | BGE-M3 BM25-heavy hybrid |
| `get_it_scope` | "Who owns…" — team ownership and boundaries | keyword (small, exact corpus) |
| `get_escalation_path` | "How do I reach / escalate…" — contact, SLA, chain | keyword (small, exact corpus) |

The worked example — *"My Workday access isn't working and I don't know who to call"* —
triggers `lookup_known_issues` (finds the SSO-loop workaround) **and** `get_it_scope` (IAM
owns it) **and** `get_escalation_path` (P1 contact + SLA) in one turn, then merges them into a
single answer. That multi-tool synthesis is the agent's job.

Three load-bearing decisions, and why:

**Native tool-use, no framework.** The orchestration loop is the raw Anthropic Messages
API — `stop_reason == "tool_use"`, dispatch the calls, batch the results back, loop. No
LangChain, no CrewAI: for a four-tool agent they add a dependency surface without changing the
design. The whole loop is [~90 lines](src/agent/orchestrator.py). The cost of going
framework-free is in *What I learned* below.

**BGE-M3 hybrid retrieval, two architectures.** The two retrieval tools use *opposite*
weightings on purpose. Process docs are natural language with high semantic variation ("take
vacation days" ↔ "PTO — Time Off Requests", zero lexical overlap) → **dense-primary**. Ticket
records are controlled enterprise vocabulary (PA30, EIB, RITM, SAP T-codes) that dense models
conflate (EIB → "bank" → wrong) → **BM25-heavy**. One embedding strategy would have lost one
of the two corpora. Full rationale and the three confirmed dense-only miss cases:
[`docs/architecture.md`](docs/architecture.md).

**Structural injection defense, not a filter.** Because the agent reads from a document
corpus, a poisoned chunk could try to hijack it. The defense is structural: an untrusted-
content rule at the top of the system prompt, every tool result JSON-enveloped so retrieved
text cannot be parsed as a new instruction turn, and a read-only tool surface so there is no
write to manipulate. Measured result: **0.0% attack success** (below). Rationale:
[`docs/threat-model.md`](docs/threat-model.md).

---

## Architecture

```
 User query
    │
    ▼
 Streamlit chat UI ──HTTP──▶ FastAPI  POST /chat
                                │
                                ▼
                    ┌─────────────────────────────────────────┐
                    │  Orchestrator — native tool-use loop      │
                    │                                           │
                    │   client.messages.create(                 │
                    │     system = cached prompt  ◀── prompt    │
                    │     tools  = cached tool defs    caching  │
                    │     messages )                            │
                    │        │                                  │
                    │        ├─ stop_reason == end_turn ─▶ done │
                    │        │                                  │
                    │        └─ stop_reason == tool_use         │
                    │              │                            │
                    │              ▼                            │
                    │     dispatch all tool_use blocks          │
                    │     ┌──────────────┬───────────────┐      │
                    │   search_*   lookup_*   get_it_scope ...  │
                    │     └──────────────┴───────────────┘      │
                    │              │                            │
                    │     batch tool_results in ONE user msg    │
                    │     (JSON-enveloped, untrusted)           │
                    │              │                            │
                    │              └──▶ loop ◀──────────────────┘
                    │                     synthesize + cite
                    └─────────────────────────────────────────┘
                                │
       Langfuse spans ◀─────────┤  (1 generation/turn + 1 span/tool,
       + token & USD cost       │   token usage on every trace)
                                ▼
                         cited answer ──▶ UI
```

Four correctness properties that are easy to get wrong in a hand-rolled loop, all verified by
[`tests/test_orchestrator.py`](tests/test_orchestrator.py):

- **Parallel tool calls** are batched into one `user` message (the API contract requires it).
- **Assistant turns** are round-tripped with `model_dump()`, not hand-rebuilt.
- **`MAX_TURNS`** caps the loop so a stuck model can't bill infinitely.
- **`is_error: true`** is set on tool exceptions so the model can recover instead of seeing a
  silent empty result.

---

## Results

Every number below is reproducible from a committed harness and dataset. Methodology,
scorer notes, and known weak spots: [`eval/REPORT.md`](eval/REPORT.md).

### Agent routing

Evaluated against a 150-query golden set ([`eval/golden/golden_set.jsonl`](eval/golden/golden_set.jsonl)).
82 queries scored; the remaining 68 hit the monthly API quota and re-run at reset
(`get_escalation_path` two-arg routing + adversarial categories pending).

| Tool | Routing accuracy | Full-answer pass |
|------|-----------------|-----------------|
| `search_process_docs` | **100%** (30/30) | 83.3% (25/30) |
| `lookup_known_issues` | **100%** (30/30) | 63.3% (19/30) |
| `get_it_scope` | **100%** (22/22) | 100% (22/22) |
| `get_escalation_path` | pending re-run | pending re-run |
| **Overall (82 scored)** | **100%** | **80.5%** |

**Routing accuracy** = required tools called in the correct order (proactive extra calls are
not penalized). **Full-answer pass** = routing correct *and* the answer contains the expected
content terms. The ~20% full-answer gap was an early corpus-coverage issue, closed by the
scaled corpus + hybrid retrieval below.

### Retrieval

Evaluated against [`eval/retrieval-gold/gold_set.jsonl`](eval/retrieval-gold/gold_set.jsonl) —
60 deliberately vocabulary-divergent query→doc pairs (queries avoid copying corpus wording to
mitigate RAGAS circularity).

| Pipeline | recall@3 | MRR@5 | NDCG@5 | RAGAS ctx recall |
|---|---|---|---|---|
| process docs (dense-primary) | **0.971** ✓ | **0.855** ✓ | 0.892 | 1.000 |
| ticket records (BM25-heavy) | **0.940** ✓ | **0.883** ✓ | 0.901 | 0.973 |

Targets: recall@3 ≥ 0.85 · MRR@5 ≥ 0.80 — **both pipelines meet both.** TF-IDF baseline
before BGE-M3: process 0.800 / 0.718, ticket 0.840 / 0.647 — the hybrid layer is worth a full
A/B, not just a claim ([`eval/REPORT.md`](eval/REPORT.md)).

### Cost (prompt caching)

The static prefix (system prompt + four tool definitions) is identical on every API call, so
it is cached with `cache_control`. Measured with `count_tokens` + live `response.usage`
([`scripts/measure_cache.py`](scripts/measure_cache.py) → [`eval/cost/REPORT.md`](eval/cost/REPORT.md)):

| Metric | Value |
|---|---|
| Static prefix | **1,785 tokens** (1,462 confirmed cached at runtime — clears the 1,024 floor) |
| Cached-read rate vs base input | **$0.30 vs $3.00 / MTok — 90% cheaper per read** |
| Prefix-input reduction, 3-call session | **51.7%** |
| Prefix-input reduction, 10-call session | **78.5%** |

Caching only discounts the static prefix; the per-turn conversation tail is uncached. The
session-level reduction climbs toward the 90% per-token ceiling as the one-time cache-write
premium amortizes over more reads — the research-expected 60–80% input-cost band lands at
5–10 call sessions.

---

## Security

This agent reads employee queries against an internal HR corpus. Two attack surfaces are
active; two are structurally closed.

| Surface | Status | Defense |
|---|---|---|
| **S1 Direct injection** — adversarial user query | Active | Untrusted-content label + role lock + explicit "must NOT" list |
| **S2 Indirect injection** — payload inside a retrieved chunk | Active | Untrusted-content label + JSON envelope isolates tool results from the instruction stream |
| **S3 Tool-call manipulation** — payload requests a write | **Closed** | Read-only architecture — no write tools exist to manipulate |
| **S4 Data exfiltration** — payload dumps all retrieved docs | Capped | Minimal-privilege returns (1,500-char excerpt cap) + read-only |

### Full red-team evaluation (v1.0)

Three runs: defended (production config), undefended baseline (D1/D3 stripped), and Garak
automated sweep. 64 total probes, 30 attack categories, 7 OWASP LLM Top 10 (2025) categories.

| Run | Probes | Successes | ASR |
|---|---|---|---|
| **Defended** (production) | 50 | 0 | **0.0%** |
| Undefended baseline | 50 | 1 | 2.0% |
| Garak (corrected) | 14 | 0 | **0.0%** |

**OWASP coverage:** LLM01 (Prompt Injection) · LLM02 (Sensitive Info Disclosure) ·
LLM06 (Excessive Agency) · LLM07 (System Prompt Leakage) · LLM08 (Vector/Embedding) ·
LLM09 (Misinformation) · LLM10 (Unbounded Consumption)

All 18 indirect payloads were *delivered* across all four tool retrieval paths — this tests
the defense against payloads that reach the model, not the retriever's luck. The single
undefended success (few-shot manipulation, `adv_022`) is fully closed by the D1
untrusted-content rule in production. The scorer uses transcript-auditable canary detection;
a quote-on-refusal false positive in the Garak sweep is documented in
[`eval/adversarial/REPORT.md`](eval/adversarial/REPORT.md). All transcripts in
[`eval/adversarial/results/`](eval/adversarial/results/).

---

## Observability

Production HR tooling has to be *inspectable* — when an answer is wrong, you need to see which
tools fired and what they returned. The agent emits [Langfuse](https://langfuse.com) traces:
one root trace per query, one generation span per LLM turn, and one span per tool dispatch,
with token usage and estimated USD cost attached to every trace
([`src/agent/tracer.py`](src/agent/tracer.py)).

Tracing is **strictly optional** — with no `LANGFUSE_PUBLIC_KEY` set, every tracer call is a
no-op and the agent runs unchanged. Token accounting runs regardless, so
`AgentResult["token_usage"]` always carries the per-query input/output/cache token counts and
cost, with or without a tracing backend.

![Langfuse trace — hr-agent-query with 1 generation span and 3 tool spans](https://raw.githubusercontent.com/nicolasduarte-data/hr-ops-agent/media/docs/screenshots/langfuse-trace.png)

---

## Limitations and Forbidden Uses

This agent is **READ-ONLY**. It cannot and must not be used to:

- Make changes to any HR system (Workday, SuccessFactors, SAP, ServiceNow)
- Approve, deny, or process any HR request or transaction
- Access or expose real employee personal data (this deployment uses only synthetic documents)
- Manage SSO, RBAC, audit trails, or multi-tenant access control
- Advise on individual employment decisions, terminations, or disciplinary actions

**What it escalates instead:** anything requiring a system write, an individual employee
decision, a compensation change, a compliance/legal judgment, or authenticated access to a
live HR system.

The production delta between this demo and a deployable system is deliberate and documented:
live HRIS APIs, SSO/RBAC, audit logging, and any write path are *out of scope by design*, not
unfinished. This runs on a synthetic corpus for a fictional company ("Meridian") and is
connected to no live system.

---

## What I learned

The honest tradeoffs behind the build:

- **Going framework-free was worth it here, but it costs you the ecosystem.** Native tool-use
  is ~90 lines I can read and debug end to end. The price: no built-in retries, no callback
  tracing, no streaming helpers — I wrote the token accounting and Langfuse wiring myself.
  For a demo that *teaches* the pattern, worth it; for a 20-tool production agent, I'd
  reconsider.

- **The interesting retrieval finding was that one strategy doesn't fit one corpus.**
  Splitting process docs (dense) from ticket records (sparse) lifted ticket recall@3 from
  0.84 to 0.94. The instinct to "just use embeddings for everything" would have quietly lost
  every PA30 / EIB / RITM lookup — the exact vocabulary HR ops runs on.

- **Measuring caching is more honest than asserting it.** "Prompt caching cuts cost 60–80%"
  is true *only* for 5–10 call sessions; a 2-call session saves 33%. Writing the measurement
  script surfaced that the headline number depends on session shape — so the README states the
  curve, not a single flattering figure.

- **Prompt injection defense is probabilistic, not a wall.** 0.0% ASR on 50 attacks is real,
  but it is RLHF-backed, not a guarantee. The ~2% undefended baseline shows the defenses are
  doing real work — not just the base model. The threat model states that plainly rather than
  implying determinism.

---

## Quick start (local)

```bash
git clone https://github.com/nicolasduarte-data/hr-ops-agent
cd hr-ops-agent
cp .env.example .env          # add your ANTHROPIC_API_KEY (Langfuse keys optional)
uv sync
uvicorn src.api.main:app --reload &   # API
streamlit run app.py                   # UI
```

---

## Stack

- **Agent:** Claude Sonnet (Anthropic API, native `tool_use` — no LangChain)
- **Retrieval:** BGE-M3 dense + sparse, RRF hybrid fusion, ChromaDB
- **API / UI:** FastAPI + uvicorn · Streamlit
- **Observability:** Langfuse traces + per-query token/cost (optional), prompt caching
- **Deploy:** Docker image built for Hugging Face Spaces (free tier); the hosted demo is offline
- **Corpus:** 42 synthetic HR documents — 9 policy/process guides + 28 ITSM ticket records +
  5 original; fictional company, real enterprise system vocabulary (SAP, Workday,
  SuccessFactors, ServiceNow, Okta)

---

## Origin

Based on a proposal to build an internal HR knowledge agent at a large enterprise (2026),
killed pre-implementation on compliance constraints. This is the public demo of what it would
have looked like — built entirely on synthetic documentation, connected to no real system.
