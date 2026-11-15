# Provenance of the 32 streaming traces

This is an inventory clarification of existing saved requests. No new benchmark or API collection was performed.

| Cohort | Traces | Model split | Inclusion |
|---|---:|---|---|
| Earlier N8 SSE (`original_N8`, `saved_trace`) | 14 | 12 v3.0 + 2 v2.5 | Original independent playback validation and extended buffer replay |
| Later SSE (`fresh_SSE`, `saved_trace`) | 6 | 3 v3.0 + 3 v2.5 | Short/medium/long comparisons and extended buffer replay |
| Measured warm WebSocket (`report4_WS`, `warm_measured`) | 10 | 5 v3.0 + 5 v2.5 | Warm TTFA results and extended buffer replay |
| Cold WebSocket warm-ups (`report4_WS`, `cold_warmup`) | 2 | 1 v3.0 + 1 v2.5 | Retained in extended offline buffer replay; excluded from measured warm TTFA |
| **Total** | **32** | **21 v3.0 + 11 v2.5** | **32 × 6 fixed prebuffers × 3 tolerances = 576 replay conditions** |

The two additional traces are **`R4-WARM-WS-3-1`** and **`R4-WARM-WS-25-1`**. They are the first synthesis requests on the respective cold sockets. The ten later warm trials use established sockets. These two socket warm-ups are separate from the two REST warm-up requests, which are not streaming traces.

The 32-trace buffer inventory includes both cold warm-ups so their arrival patterns remain inspectable. They do not enter the reported five-per-model warm TTFA medians or the 5/5 versus 0/5 warm underrun comparison. Earlier N8, later SSE and warm WS results remain separate cohorts. Repeated traces/policies are not independent texts, speakers or live handset calls.

Canonical exports: [all 32 request records](results/report4/stream_trials.csv), [all recorded chunk arrivals](results/report4/stream_chunk_timeline.csv), [all 576 buffer/tolerance conditions](results/report4/buffer_sensitivity.csv). The request ledger includes each source audio/timeline path and SHA-256. Every source file and digest was checked during this final repository review.

## Exact two cold warm-up requests

- **R4-WARM-WS-3-1** — timbre-v3.0; request ID `R4-WARM-WS-3-1-report4-ws-98ae78b1`. [Saved PCM](results/report4/audio/ws/R4-WARM-WS-3-1-report4-ws-98ae78b1.wav) · [Saved arrival events](results/report4/raw/tts_ws/R4-WARM-WS-3-1/R4-WARM-WS-3-1-report4-ws-98ae78b1.json).
- **R4-WARM-WS-25-1** — timbre-v2.5; request ID `R4-WARM-WS-25-1-report4-ws-1c8f43b6`. [Saved PCM](results/report4/audio/ws/R4-WARM-WS-25-1-report4-ws-1c8f43b6.wav) · [Saved arrival events](results/report4/raw/tts_ws/R4-WARM-WS-25-1/R4-WARM-WS-25-1-report4-ws-1c8f43b6.json).

## Full 32-trace inventory

| # | Case ID | Cohort / phase | Model | Saved source evidence |
|---|---|---|---|---|
| 1 | `N8-en-IN-short` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-en-IN-short__timbre-v3.0-8000.wav) · [events](results/next/raw/tts_stream/N8-en-IN-short/timbre-v3.0-8000.json) |
| 2 | `N8-en-IN-medium` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-en-IN-medium__timbre-v3.0-24000.wav) · [events](results/next/raw/tts_stream/N8-en-IN-medium/timbre-v3.0-24000.json) |
| 3 | `N8-en-IN-medium` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-en-IN-medium__timbre-v3.0-8000.wav) · [events](results/next/raw/tts_stream/N8-en-IN-medium/timbre-v3.0-8000.json) |
| 4 | `N8-en-IN-long` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-en-IN-long__timbre-v3.0-24000.wav) · [events](results/next/raw/tts_stream/N8-en-IN-long/timbre-v3.0-24000.json) |
| 5 | `N8-en-IN-long` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-en-IN-long__timbre-v3.0-8000.wav) · [events](results/next/raw/tts_stream/N8-en-IN-long/timbre-v3.0-8000.json) |
| 6 | `N8-hi-IN-short` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-hi-IN-short__timbre-v3.0-24000.wav) · [events](results/next/raw/tts_stream/N8-hi-IN-short/timbre-v3.0-24000.json) |
| 7 | `N8-hi-IN-short` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-hi-IN-short__timbre-v3.0-8000.wav) · [events](results/next/raw/tts_stream/N8-hi-IN-short/timbre-v3.0-8000.json) |
| 8 | `N8-hi-IN-medium` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-hi-IN-medium__timbre-v3.0-24000.wav) · [events](results/next/raw/tts_stream/N8-hi-IN-medium/timbre-v3.0-24000.json) |
| 9 | `N8-hi-IN-medium` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-hi-IN-medium__timbre-v3.0-8000.wav) · [events](results/next/raw/tts_stream/N8-hi-IN-medium/timbre-v3.0-8000.json) |
| 10 | `N8-hi-IN-long` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-hi-IN-long__timbre-v3.0-24000.wav) · [events](results/next/raw/tts_stream/N8-hi-IN-long/timbre-v3.0-24000.json) |
| 11 | `N8-hi-IN-long` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-hi-IN-long__timbre-v3.0-8000.wav) · [events](results/next/raw/tts_stream/N8-hi-IN-long/timbre-v3.0-8000.json) |
| 12 | `N8-en-IN-short` | `original_N8` / `saved_trace` | timbre-v3.0 | [PCM](results/next/audio/stream/N8-en-IN-short__timbre-v3.0-24000.wav) · [events](results/next/raw/tts_stream/N8-en-IN-short/timbre-v3.0-24000.json) |
| 13 | `N8-en-IN-medium` | `original_N8` / `saved_trace` | timbre-v2.5 | [PCM](results/next/audio/stream/N8-en-IN-medium__timbre-v2.5-8000.wav) · [events](results/next/raw/tts_stream/N8-en-IN-medium/timbre-v2.5-8000.json) |
| 14 | `N8-hi-IN-medium` | `original_N8` / `saved_trace` | timbre-v2.5 | [PCM](results/next/audio/stream/N8-hi-IN-medium__timbre-v2.5-8000.wav) · [events](results/next/raw/tts_stream/N8-hi-IN-medium/timbre-v2.5-8000.json) |
| 15 | `NF-S-3-short` | `fresh_SSE` / `saved_trace` | timbre-v3.0 | [PCM](results/timbre_followup/audio/stream/NF-S-3-short-run1-sse-b05bf6b8.wav) · [events](results/timbre_followup/raw/tts_stream/NF-S-3-short/NF-S-3-short-run1-sse-b05bf6b8.json) |
| 16 | `NF-S-25-short` | `fresh_SSE` / `saved_trace` | timbre-v2.5 | [PCM](results/timbre_followup/audio/stream/NF-S-25-short-run1-sse-0a330aa0.wav) · [events](results/timbre_followup/raw/tts_stream/NF-S-25-short/NF-S-25-short-run1-sse-0a330aa0.json) |
| 17 | `NF-S-3-medium` | `fresh_SSE` / `saved_trace` | timbre-v3.0 | [PCM](results/timbre_followup/audio/stream/NF-S-3-medium-run1-sse-c4c03237.wav) · [events](results/timbre_followup/raw/tts_stream/NF-S-3-medium/NF-S-3-medium-run1-sse-c4c03237.json) |
| 18 | `NF-S-25-medium` | `fresh_SSE` / `saved_trace` | timbre-v2.5 | [PCM](results/timbre_followup/audio/stream/NF-S-25-medium-run1-sse-8a0f516f.wav) · [events](results/timbre_followup/raw/tts_stream/NF-S-25-medium/NF-S-25-medium-run1-sse-8a0f516f.json) |
| 19 | `NF-S-3-long` | `fresh_SSE` / `saved_trace` | timbre-v3.0 | [PCM](results/timbre_followup/audio/stream/NF-S-3-long-run1-sse-7cf71a29.wav) · [events](results/timbre_followup/raw/tts_stream/NF-S-3-long/NF-S-3-long-run1-sse-7cf71a29.json) |
| 20 | `NF-S-25-long` | `fresh_SSE` / `saved_trace` | timbre-v2.5 | [PCM](results/timbre_followup/audio/stream/NF-S-25-long-run1-sse-bd8fb381.wav) · [events](results/timbre_followup/raw/tts_stream/NF-S-25-long/NF-S-25-long-run1-sse-bd8fb381.json) |
| 21 | `R4-WARM-WS-3-1` | `report4_WS` / `cold_warmup` | timbre-v3.0 | [PCM](results/report4/audio/ws/R4-WARM-WS-3-1-report4-ws-98ae78b1.wav) · [events](results/report4/raw/tts_ws/R4-WARM-WS-3-1/R4-WARM-WS-3-1-report4-ws-98ae78b1.json) |
| 22 | `R4-WS-3-short-1` | `report4_WS` / `warm_measured` | timbre-v3.0 | [PCM](results/report4/audio/ws/R4-WS-3-short-1-report4-ws-b720f480.wav) · [events](results/report4/raw/tts_ws/R4-WS-3-short-1/R4-WS-3-short-1-report4-ws-b720f480.json) |
| 23 | `R4-WS-3-short-2` | `report4_WS` / `warm_measured` | timbre-v3.0 | [PCM](results/report4/audio/ws/R4-WS-3-short-2-report4-ws-74325191.wav) · [events](results/report4/raw/tts_ws/R4-WS-3-short-2/R4-WS-3-short-2-report4-ws-74325191.json) |
| 24 | `R4-WS-3-short-3` | `report4_WS` / `warm_measured` | timbre-v3.0 | [PCM](results/report4/audio/ws/R4-WS-3-short-3-report4-ws-d6651769.wav) · [events](results/report4/raw/tts_ws/R4-WS-3-short-3/R4-WS-3-short-3-report4-ws-d6651769.json) |
| 25 | `R4-WS-3-short-4` | `report4_WS` / `warm_measured` | timbre-v3.0 | [PCM](results/report4/audio/ws/R4-WS-3-short-4-report4-ws-1af2a437.wav) · [events](results/report4/raw/tts_ws/R4-WS-3-short-4/R4-WS-3-short-4-report4-ws-1af2a437.json) |
| 26 | `R4-WS-3-short-5` | `report4_WS` / `warm_measured` | timbre-v3.0 | [PCM](results/report4/audio/ws/R4-WS-3-short-5-report4-ws-7aef4902.wav) · [events](results/report4/raw/tts_ws/R4-WS-3-short-5/R4-WS-3-short-5-report4-ws-7aef4902.json) |
| 27 | `R4-WARM-WS-25-1` | `report4_WS` / `cold_warmup` | timbre-v2.5 | [PCM](results/report4/audio/ws/R4-WARM-WS-25-1-report4-ws-1c8f43b6.wav) · [events](results/report4/raw/tts_ws/R4-WARM-WS-25-1/R4-WARM-WS-25-1-report4-ws-1c8f43b6.json) |
| 28 | `R4-WS-25-short-1` | `report4_WS` / `warm_measured` | timbre-v2.5 | [PCM](results/report4/audio/ws/R4-WS-25-short-1-report4-ws-466aa59b.wav) · [events](results/report4/raw/tts_ws/R4-WS-25-short-1/R4-WS-25-short-1-report4-ws-466aa59b.json) |
| 29 | `R4-WS-25-short-2` | `report4_WS` / `warm_measured` | timbre-v2.5 | [PCM](results/report4/audio/ws/R4-WS-25-short-2-report4-ws-5385b8c7.wav) · [events](results/report4/raw/tts_ws/R4-WS-25-short-2/R4-WS-25-short-2-report4-ws-5385b8c7.json) |
| 30 | `R4-WS-25-short-3` | `report4_WS` / `warm_measured` | timbre-v2.5 | [PCM](results/report4/audio/ws/R4-WS-25-short-3-report4-ws-fb9f1dec.wav) · [events](results/report4/raw/tts_ws/R4-WS-25-short-3/R4-WS-25-short-3-report4-ws-fb9f1dec.json) |
| 31 | `R4-WS-25-short-4` | `report4_WS` / `warm_measured` | timbre-v2.5 | [PCM](results/report4/audio/ws/R4-WS-25-short-4-report4-ws-25dc001c.wav) · [events](results/report4/raw/tts_ws/R4-WS-25-short-4/R4-WS-25-short-4-report4-ws-25dc001c.json) |
| 32 | `R4-WS-25-short-5` | `report4_WS` / `warm_measured` | timbre-v2.5 | [PCM](results/report4/audio/ws/R4-WS-25-short-5-report4-ws-95913cd2.wav) · [events](results/report4/raw/tts_ws/R4-WS-25-short-5/R4-WS-25-short-5-report4-ws-95913cd2.json) |
