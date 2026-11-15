# Report 4 — verified changes and implementation

Source: Gnani_Final_Benchmark_Improvements_Report4.docx. The original document is retained locally unchanged. This is a targeted extension; original ASR and human TTS cohorts are not silently rescored or merged.

## Implementation status

| Requested improvement | Status | Evidence |
|---|---|---|
| Controlled REST / RTF | Completed | Five successful repeats for each model × length, two excluded warm-ups, seeded balanced order; rest_latency_trials.csv and rest_latency_summary.csv |
| Separate first-playable audio timing | Completed | Five warm short-prompt WebSocket trials/model; cold connection warm-ups excluded; stream_trials.csv |
| Attempt-level empty-audio / retry audit | Completed | REST and SSE mapped to case/retry/recheck IDs; positive PCM checks; tts_http_attempts.csv |
| Buffer-versus-underflow tradeoff | Completed offline | 32 saved traces × six buffers × three tolerances = 576 conditions; plots and playback examples |
| Blinded quality panel | Audio/material prepared; human collection pending | 33 successful clips of 34 planned, 15 matched neutral pairs plus extra material; anonymous L1/L2/L3 sheet |
| Held-out TTS rewrites | Ten pairs generated; human correctness pending | Frozen rules, 20 v2.5 outputs, tts_rewrite_pairs.csv; no outcome is inferred from audio generation |
| Held-out ASR keyterms | Completed | Frozen generic vocabulary; 15 unused public banking recordings; paired source-reference WER/CER and lexical diagnostics |
| Replay, PDF and package gate | Rebuilt and verified by release checks | Standard replay command, exact two-page PDFs, notebook and source hashes |
| Live interruption / handset reliability | Not performed | Existing unit cleanup tests and offline buffer replays do not establish live cancellation or phone behavior |

## Controlled timing findings

Same English strings (61/396/930 characters), language en-IN, speed 1.0, mono PCM16 at 24 kHz, same client/account/endpoint. Effective request settings and text SHA-256 are retained. Model-specific voices Tarika and Kaveri differ. No overlapping synthesis; five measured successes per cell; warm-ups excluded. No tiny-sample p95 is presented.

| Model / length | Successful / HTTP attempts | REST median (range), s | Decoded audio median, s | Client RTF median |
|---|---:|---:|---:|---:|
| timbre-v3.0 / short | 5/5 | 3.437 (1.005–5.424) | 3.52 | 0.976 |
| timbre-v3.0 / medium | 5/5 | 6.504 (3.004–7.599) | 22.72 | 0.324 |
| timbre-v3.0 / long | 5/5 | 11.747 (9.000–16.007) | 52.88 | 0.222 |
| timbre-v2.5 / short | 5/5 | 0.767 (0.731–1.164) | 3.04 | 0.254 |
| timbre-v2.5 / medium | 5/5 | 1.183 (1.164–1.355) | 17.76 | 0.067 |
| timbre-v2.5 / long | 5/5 | 2.564 (2.474–2.944) | 42.56 | 0.059 |

V3.0 produces longer audio on these prompts, yet its client-visible RTF is also higher. The cause of its response-time difference is unresolved: client clocks do not separate model compute, queueing, preprocessing or network transfer. The earlier three-repeat medians remain versioned in TIMBRE_FOLLOWUP.md; variability between collections is not evidence of a provider-side fix.

Warm short-prompt WebSocket TTFA:

- timbre-v3.0: 813.0 ms median; 267.5–3015.5 ms range; 5/5 successes.
- timbre-v2.5: 161.3 ms median; 156.6–171.5 ms range; 5/5 successes.

These TTFA values exclude handshake/cold warm-up and measure first playable PCM, not semantic speech onset. V3.0 immediate playout underruns in all five warm trials; v2.5 in none of five.

## Disjoint request audit

| Cohort | Cases | HTTP attempts | Valid PCM | Empty PCM | HTTP errors | Attempt success | Eventual case success |
|---|---:|---:|---:|---:|---:|---:|---:|
| timbre_followup | 73 | 74 | 66 | 6 | 2 | 89.19% | 90.41% |
| report4_controlled | 32 | 32 | 32 | 0 | 0 | 100.00% | 100.00% |
| report4_quality | 54 | 54 | 53 | 1 | 0 | 98.15% | 98.15% |

The original 74 attempts include six SSE HTTP requests, not just REST. Their disjoint outcomes are 66 valid PCM, six empty PCM, one HTTP 500 and one intentionally invalid tag-only HTTP 400. One retry recovered the HTTP 500; eight separately named rechecks are not retries. Thus 66/74 attempt success differs from 66/73 eventual case success; excluding the intended negative case gives 66/72 positive-case success. Diagnostic cases and rechecks preclude interpreting these as production failure rates.

The controlled cohort has 32 REST requests: 30 measured + two excluded warm-ups, all valid. Its separate 12 WebSocket requests (ten warm measured + two cold warm-ups) are in stream_trials.csv rather than double-counted as HTTP synthesis requests. The new listening/rewrite cohort has 54 REST cases, 53 valid and one additional v3.0 header-only response.

Every saved returned WAV is decoded and counted. Zero PCM is an application/service failure even at HTTP 200. Placeholder WAV length fields with valid PCM are a separate client-compatibility issue. The prior 48 kHz rechecks did not consistently resolve empty audio. SSE wire-response byte counts were not saved; saved decoded WAV bytes are explicitly distinguished and wire size is left unavailable. REST per-attempt timing and inferred retry gaps are separate from terminal retry-inclusive timing.

## Buffer tradeoff

Fixed prebuffers 0/50/100/200/500/1000 ms are replayed on identical arrivals. Tolerances 1/10/20 ms change counted underruns, not physical silence. All 32 stream chunk totals match decoded samples. The log exports arrival time, chunk sample count/duration, cumulative received audio and playable buffer before/after each arrival. Provider-side generation timestamps are unavailable.

At 1000 ms, two of three earlier fresh v3.0 SSE traces and three of five new warm v3.0 WS traces still underrun. Corresponding v2.5 controls remain continuous. Added prebuffer increases simulated startup by exactly that buffer; it is not a newly measured TTFA. Future-aware minimum stall-free start remains a separate non-causal bound. No production jitter-buffer threshold is selected.

Open [the controlled timing / buffering evidence](results/report4/index.html). Source exports: results/report4/rest_latency_trials.csv, tts_http_attempts.csv, stream_chunk_timeline.csv, buffer_sensitivity.csv and buffer_summary.csv.

## Held-out ASR result

Generic financial keyterms were frozen before new source selection or model predictions. The old SVQ inventory had too few unused clean financial-term utterances, so 15 public [MInDS-14 banking recordings](https://huggingface.co/datasets/PolyAI/minds14) were selected under the unchanged vocabulary. Dataset original transcriptions are used; source revision, hashes and CC-BY-4.0 attribution are retained. These are US-English examples with the supported en-IN API hint; speaker identities are unavailable. They are separate from the original 370 inputs.

Paired results: 29/150 → 28/150 word edits, WER **19.33% → 18.67%**, CER **15.83% → 15.25%**. One clip improved, 14 unchanged, none regressed. The only represented frozen target term is “account”: recall is 14/15 → 15/15; bank-name/acronym benefit is not established. Source audio is 8 kHz. No absent-reference hinted-vocabulary insertion flags were found. This small selected result does not establish a general gain. Critical-slot exports check literal target terms, numeric-string order and negative-marker presence; they are not full semantic transaction correctness.

## Human quality and held-out rewrite study

No new human scores are invented or imported from earlier clips. Quality: 16 unique texts planned in both models plus two separate supported-tag outputs; one neutral v3.0 request returned empty. There are 33 successful outputs, with 15 complete version-neutral pairs, two tagged variants and one unmatched v2.5 output. Matched model comparisons must exclude the unmatched text; tagged outputs form a separate condition.

Open [the blinded listening page](results/report4_quality/listening.html). Work independently as L1/L2/L3, declare language familiarity, listen/transcribe before revealing the reference, then score naturalness, intelligibility, pronunciation, prosody and expressiveness on the anchored 1–5 rubric. Do not inspect tts_listening_key.csv until ratings are submitted. Exported listener CSVs contain real marks only; blank rows are excluded. Existing voice familiarity may reduce blinding.

Open [the ten held-out raw/rewrite pairs](results/report4_quality/rewrites.html). Frozen rules expand minus signs, currency, dates/times and identifier zeros while preserving negation. These are English v2.5/Kaveri pairs only. Fill tts_rewrite_pairs.csv with independent correctness marks, then count fixed / newly broken / both correct / both wrong. Twenty generated files alone do not establish preprocessing benefit.

## Final report edits and limits

- The main PDF stays two pages; original 164 clips, prior 66 valid follow-up outputs and new controlled/listening sets are distinct.
- Short/medium/long refer to input text sizes; REST full-body wait, PCM duration, client RTF and streaming TTFA use separate columns.
- Exercising v3.0 tags establishes feature coverage; superior perceived quality remains unestablished. Earlier automated ratings are provisional and missed a planted gap.
- V2.5 was more promising in tested playback configurations. Larger paired and real-handset tests are required before deployment choice.
- Cause of v3.0 delay remains unresolved. No GPU, architecture, queueing or universal model-superiority claim is made.
- Native listening, scored held-out TTS rewrite outcomes, live interruption/late-audio cancellation, handset/Exotel behavior and extended-load production safety remain unvalidated.

## Reproduce

`python run_evaluation.py --mode replay --part all --reports` rebuilds all source-reference/human scores and the separate Report-4 extensions without new API calls. `python scripts/build_timbre_comparison.py` refreshes the portable 18-clip comparison to the controlled five-repeat REST cohort. Paid collection scripts require explicit --live flags, frozen manifests and the existing budget guard.

Human score import after independent review: `python scripts/import_report4_listening.py listener_L1.csv listener_L2.csv --apply`. Omit `--apply` to validate only. Conflicting/duplicate or invalid marks are rejected; empty score rows add no evidence. Replay then reports clip means/medians, listener ranges and condition summaries.


## Final REST sample-count clarification

The controlled comparison uses one text per short/medium/long group: 2 models × 3 texts × 5 successful repeats = **30 measured requests**, plus **two excluded warm-ups** (32 controlled REST requests total). The **60 completed REST files** refer to a separate earlier waveform-check set: **18 earlier timing runs + 42 functionality/configuration outputs**. These earlier files are not pooled into the controlled timing medians. Per-case memberships and source IDs are in results/submission/rest_cohort_membership.csv; the sets share no case IDs.

## Final submission clarification

**Streaming provenance:** 32 traces = 14 earlier N8 SSE + 6 later SSE + 10 measured warm WebSocket + 2 cold WebSocket warm-ups. The additional IDs are `R4-WARM-WS-3-1` and `R4-WARM-WS-25-1`. Cold warm-ups are retained in the 576 offline buffer conditions and excluded from warm TTFA medians. See [the full provenance inventory](STREAMING_TRACE_PROVENANCE.md).

**Human validation status:** the new three-listener quality panel and ten held-out TTS rewrite pairs are **prepared, awaiting scores**. Their audio generation is complete; their human evaluations are not completed tests and contribute no new quality/correctness results. Existing historical human marks and the completed held-out ASR experiment are separate.

From this `evidence/` repository directory, run `python run_evaluation.py --mode replay --part all --reports`. The final executed submission notebook is [../final_evaluation.ipynb](../final_evaluation.ipynb); start there when reviewing all completed public stages and their retained outputs.
