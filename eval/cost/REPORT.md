# Prompt Caching — Cost Measurement

*Generated 2026-06-04 · model `claude-sonnet-4-6` · `scripts/measure_cache.py`*

## Static prefix

- **1,785 tokens** (system prompt + 4 tool definitions), measured with `count_tokens` (free, unbilled).
- **1,462 tokens** actually written to cache at runtime (`cache_creation_input_tokens`).
- Threshold: 1,024 tokens — **met** ✓ caching active on both measures.

> **The 1,785 vs 1,462 difference** is the tool-use scaffolding Anthropic injects
> into the request, which `count_tokens` includes but which sits outside the
> cacheable span. The runtime `cache_creation_input_tokens` reflects what is
> actually cached. Both clear the 1,024-token floor.

## Live measurement (real `response.usage`)

Cold cache (first invocation of the session):

| Event | Tokens | Rate | Note |
|---|---|---|---|
| Cache write (call 1) | 1,462 | $3.75 / MTok | one-time, 1.25× base |
| Cache read (call 2) | 1,462 | $0.30 / MTok | every cached hit, 0.10× base |
| Plain input control (no `cache_control`) | 1,813 | $3.00 / MTok | full reprocess every call |

The cache-read count **exactly matching** the cache-write count confirms the
entire prefix was served from cache, not reprocessed.

**Cross-run TTL persistence (observed):** an immediate second run re-read the same
1,462-token prefix from cache while writing only 348 new tokens — the prefix from
the prior run was still live inside Anthropic's ~5-minute cache TTL. Under steady
demo traffic the prefix stays warm and nearly every call pays the read rate, not
the write rate.

## Session cost delta (3-call multi-tool session)

Caching only affects the static prefix; the conversation tail is identical in
both runs and cancels. Prefix-input cost:

| Variant | Prefix-input cost | Per cached call |
|---|---|---|
| Uncached | $0.016065 | $3.00 / MTok |
| Cached | $0.007765 | $0.30 / MTok (read) |
| **Reduction** | **51.7%** | 10× cheaper per read |

Formula:
```
uncached = n_calls × prefix × $3.00/MTok
cached   = prefix × $3.75/MTok (write)  +  (n_calls-1) × prefix × $0.30/MTok (reads)
```

On the static prefix tokens specifically, every cached call costs
**$0.30/MTok vs $3.00/MTok — a 90% reduction**; the session-level figure is lower
because the first call pays the one-time cache write.

### Reduction by session length

The session-level reduction climbs toward the 90% per-token ceiling as the
one-time write premium amortizes over more cached reads:

| Calls in session | Prefix-input reduction |
|---|---|
| 2 | 32.5% |
| 3 | 51.7%  ← typical routing path |
| 5 | 67.0% |
| 10 | 78.5% |

The research target (T1: 60–80% input-cost reduction) is realized at 5–10 call
sessions; a typical 2–3 call HR routing path saves ~33–52% on the prefix while
every individual cached read is 90% cheaper.
