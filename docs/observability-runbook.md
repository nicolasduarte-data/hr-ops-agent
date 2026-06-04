# Observability Runbook — Langfuse Tracing & Retrieval Health

Operational guide for confirming and debugging the agent's observability on Hugging Face
Spaces. Read this before concluding "tracing is broken."

---

## The two sidebar status chips

The Streamlit app renders a **System status** panel in the sidebar with two independent
signals. Both are visible at a glance on the live Space.

| Chip | Green | Yellow / Red |
|---|---|---|
| **Langfuse tracing** | `🟢 Langfuse tracing active` + the host region | `🟡 disabled` (keys/pkg missing) or `🔴 init error` |
| **Retrieval** | `🟢 Retrieval: BAAI/bge-m3` | `🟡 fallback: <model>` or `🟡 keyword fallback` |

> **Key distinction:** the Langfuse chip confirms the client **initialised** — it does NOT
> confirm events were **delivered**. Green is necessary, not sufficient. Always confirm a
> trace actually appears in the dashboard.

---

## Confirming tracing works (the happy path)

1. Open the Space. Sidebar Langfuse chip should read **🟢** and show the host
   (e.g. `https://us.cloud.langfuse.com`).
2. Send any query.
3. Open the Langfuse dashboard → your project → **Tracing**. A `hr-agent-query` trace should
   appear within a few seconds, with 1 generation span + 1 span per tool call.

If all three hold, observability is healthy. Done.

---

## Decision tree — "tracing isn't working"

### Symptom: sidebar chip is 🟡 / 🔴

The Langfuse client did not initialise. Causes, in likelihood order:

1. **`langfuse` v3/v4 installed instead of v2.** HF installs from `requirements.txt`, which
   pins `langfuse>=2.0.0,<3.0.0`. v3/v4 removed `lf.trace()` / `trace.span()`, which the
   tracer depends on — the first trace call raises and is swallowed. If the chip is yellow
   after a deploy, HF likely served a **cached build** and skipped the reinstall.
   → **Fix:** HF Space → Settings → **Factory rebuild** (not "Restart" — restart reuses the
   image and won't reinstall). Confirm in build logs: `Successfully installed langfuse-2.x`.
2. **Keys not set.** Space → Settings → Variables and secrets must have
   `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`.
3. **`🔴 init error`** — check the Space logs for the tracer exception traceback.

### Symptom: chip is 🟢 but the dashboard stays empty

The client initialised but events aren't landing. Two suspects, in order:

1. **Region mismatch (most common).** The chip prints the host. It must match the region your
   Langfuse account lives in:
   - US account → `https://us.cloud.langfuse.com`
   - EU account → `https://cloud.langfuse.com`
   If the chip shows the wrong region, fix the `LANGFUSE_HOST` secret and factory-rebuild.
   Confirm in logs: `Langfuse tracing enabled → <host>`.
2. **Flush not reached.** The app calls `get_tracer().flush()` after each successful query
   (Streamlit direct mode) and the API path flushes per-request + on shutdown. A query that
   **errors** won't flush its own trace until the next successful query flushes the queue.
   Send a second, valid query and recheck.

---

## Retrieval health ("loaded too fast" / wrong model)

The retrieval chip shows which embedding model is actually live. The model falls back silently
by design (BGE-M3 → bge-small → TF-IDF → keyword), so this chip is how you catch a silent
downgrade.

- **🟢 `BAAI/bge-m3`** — full hybrid retrieval; matches the README's metrics.
- **🟡 `bge-small-en-v1.5`** — dense-only fallback (disk/network constraint at build).
- **🟡 `tfidf-fallback`** — last-resort lexical; CI/degraded only.
- **🟡 keyword fallback** — retrieval layer didn't load at all; tools use naive keyword search.

If the Space "loaded suspiciously fast" and the chip is **not** green, BGE-M3 didn't download
(it's a ~2.2 GB pull on cold start). Check the Space logs for the `_load_model` warnings, and
confirm free disk ≥ 2.4 GB. To force BGE-M3 and fail loudly instead of falling back, set the
Space variable `BGE_M3_REQUIRED=1`.

---

## Deploying changes to the Space

Do **not** `git push huggingface master` directly — it's rejected because origin's history
contains a binary blob HF's hook refuses (see `scripts/deploy-hf.sh` header for the full why).

Instead:

```bash
git push origin master          # push your changes to GitHub first
bash scripts/deploy-hf.sh       # sync master's tree → HF, no blob, one command
```

Then watch the Space logs for the rebuild, and re-run the happy-path confirmation above.
