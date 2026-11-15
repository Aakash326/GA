# Methods and verification

## Submission scope

The default runner profile evaluates only public ASR audio and original dataset transcripts. Private call inputs and adjudicated reference substitutions do not contribute to headline recognition scores. TTS correctness uses explicit human marks only; unmarked targets are excluded. The working archive retains exploratory provenance. Private input records, score-only rows, restricted summaries/charts and older notebooks are excluded from the public ZIP; the released notebook is gnani_submission.ipynb.

ASR inputs: baseline 226 = 221 speech + five no-speech controls; follow-up 120 = 20 per language; extension 24 = 12 finance questions + 12 technical Hindi-English tutorial utterances. No audio hashes/source utterance IDs overlap across cohorts, but speaker IDs do. Transformations retain their parent/source IDs and are not independent speakers. Hindi baseline groups the first locale and includes Hindi-English hints. Different-cohort language percentages are not before/after model gains.

The public source/reference policy is why headline values differ from the exploratory report. This is a scope/measurement change; no new model run or improvement is implied. Source dataset transcripts can contain errors; their uncertainty limits absolute accuracy claims.

## ASR metrics

`evaluation_metrics.py` implements custom Levenshtein distance and deterministic S/D/I backtrace. Corpus WER = sum(word edits) / sum(reference words), not the mean of clip WERs. CER aligns Unicode code points; CER without spaces is exported separately. Raw scoring applies NFC, case folding and collapsed whitespace. Normalized scoring additionally maps Unicode digits and removes punctuation while preserving numeric signs, decimals, time colons and currency/percent symbols. Cross-script differences remain errors; semantic equivalence is not inferred.

Empty-reference controls have undefined WER/CER, exported as empty fields. They are excluded from speech totals; false transcription and inserted-word counts are separate outcomes. WER above 100% can be valid. The source-reference baseline is 309/1,630 = 18.957%; follow-up 186/881 = 21.112%; extension 48/249 = 19.277%. The runner asserts these edit/reference totals and checks every public input hash.

## Human TTS content scores

| Cohort | Generated clips | Human-scored clips | Human targets | Correct | Wrong | Ambiguous |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 98 | 38 | 62 | 57 | 4 | 1 |
| Follow-up | 66 | 28 | 48 | 35 | 12 | 1 |

A prompt/clip may contain multiple targets. Ambiguous counts as not correct under the strict rule but is not a confirmed omission. Critical baseline targets: 53/58 correct; follow-up: 35/48. Target definitions retain sign, leading-zero, order and negation requirements. These are intentionally selected diagnostic subsets, not population or representative language accuracy.

The separate 50-clip review comprises 24 flagged clips, 16 paired counterparts and 10 category/language coverage clips. Its marks overlap the table: baseline 26/29 targets, follow-up 48/60, total 74/89 (56 correct, 16 wrong, two ambiguous). Fifteen blank targets add no human scores. Older explicit listening marks outside this subset also contribute to the baseline human totals. Identity/language declarations are missing in that export; blind-first flags are false. No independent or native-qualified listening is inferred.

Nine raw/rewrite pairs have complete human marks on both variants: eight fixed, one failed both. This error-enriched selection does not estimate general rewrite effectiveness. ASR keyterms were also derived from observed errors; their paired gain remains an oracle-aided demonstration. New vocabulary/rewrites must be fixed before inspecting held-out predictions.

## Naturalness and prosody — actual existing ratings

Human source: `results/listening_ratings.csv`, listener R1, 13 November 2026. Clip-level ratings were repeated once per content target. Deduplicate by clip, listener and timestamp; conflicting duplicate scores would fail validation.

| Clip | Naturalness / 5 | Prosody / 5 | Repeated target rows |
|---|---:|---:|---:|
| T36 | 4 | 5 | 2 |
| T43 | 4 | 5 | 1 |
| T49 | 5 | 5 | 1 |
| T70 | 5 | 5 | 3 |

Four clip ratings, one listener: naturalness mean/median 4.50/5; prosody mean/median 5.00/5. Seven target rows are not seven independent ratings. This is a small selected sample, with non-blind/not-recorded reveal order and incomplete language qualifications. It does not establish population MOS or naturalness across all 164 clips/languages. No new ratings are invented. The prepared 12-clip study remains an expansion step, not a replacement for these actual measurements.

## Objective audio quality

All 164 generated WAVs are checked for nonempty PCM16 mono decoding, duration, sample rate, level and low-energy intervals. Near-full-scale means absolute PCM value >=32,760 (out of 32,768). Four clips contain such samples; this is a level flag, not proof of audible clipping. RMS is measured in 20 ms frames; low energy is below -50 dBFS. Twenty-two clips have an internal interval >0.5 s; maximum 1.16 s. Leading/trailing low energy is excluded from the internal measure. These intervals can be intentional pauses. All 164 REST WAVs have unknown-length placeholder frame counts. Analysis bounds reads by actual file bytes, counts decoded PCM samples, and uses those durations rather than advertised header lengths. Maximum actual clip duration is 74.72 s. Remux decoded audio when clients require finite WAV sizes. Objective diagnostics do not produce or replace a naturalness score.

## Independent playback stall benchmark

`scripts/validate_playback.py` is separate from the original floating-duration calculation. For each of the 14 saved N8 traces it:

1. Confirms mono PCM16 sample rate and that sum(chunk bytes / 2) equals the saved WAV frame count.
2. Checks logged rounded chunk durations against byte-derived exact durations.
3. Converts arrival timestamps to integer samples, then schedules each actual PCM chunk into a playback WAV. Initial zeros represent startup; inserted zeros after playback starts represent late chunk underruns.
4. Counts gaps exceeding a 1 ms tolerance. All 12 v3.0 streams have gaps; both v2.5 controls have none.
5. Computes earliest gap-free start as max(arrival sample - prior audio samples) and reconstructs the delayed version. All 14 delayed versions are gap-free. This policy sees future arrivals, so it is diagnostic rather than an online buffer guarantee.
6. Exports audio/timeline SHA-256, exact frames, gap sample positions/durations and 28 playable WAVs. Open `results/playback_validation/index.html`.

Exact v3.0 extra wait is 844.833–3,910.917 ms. The old duration-rounding error is at most 1.183 ms; the reported 0.84–3.91 s range remains consistent. Buffer sensitivity replays the identical arrivals/PCM with fixed 0/50/100/200 ms initial prebuffers and reporting tolerances of 1/10/20 ms (168 rows). It exports underflow count, total physical starvation, counted starvation, startup delay and the retrospective final-underrun end. Tolerance changes the reported count, not the actual schedule or total starvation. All tested v3.0 streams still underrun in all conditions; both v2.5 controls do not. These small configuration-specific controls do not establish general model superiority. This verifies the saved benchmark and renders its audible effect; it is not a fresh live/network/device test. The sound-then-silence finding means temporary underruns, not permanent silence.

## Latency and load methods

REST latency spans dispatch to full response body, before local decode; RTF divides by decoded audio duration. Retry-inclusive timing includes backoff. REST has at most four attempts, waiting 1, 2 and 4 s between attempts after retryable network errors or HTTP 429/500/502/503/504. SSE is a single stream attempt; decode failure invalidates TTS HTTP success.

First audio is the first decoded playable chunk from synthesis dispatch. Warm WebSocket measurements use an existing connection; cold totals include handshake. ASR final-transcript timing is relative to clip end, includes VAD/network behavior and can precede trailing silence. The first concurrency round is reported separately from later attempts. Client dispatch-to-body intervals estimate in-flight requests, not provider queues or concurrent phone calls.

Collection: 13–14 November 2026, tested account/request mix/models/voices; region was not recorded. Complete response headers and some server IDs were not logged and are not invented. Saved requests/statuses/timestamps and raw chunk timings remain in the diagnostics. Published latency/RTF are rebuilt from request IDs and actual decoded PCM lengths: 221 public ASR speech timings, 98 baseline TTS clips, 30 short-prompt connection runs and the 18 paired streaming clips. Additional pilot streams are excluded from that paired latency cohort. Per-run traces and cold-handshake calculations are exported, and concurrency/soak successes are rebuilt from first-round terminal attempts. The 30-request short soak does not establish extended-load reliability.

## Expanded human study and rollout

The 12-clip study HTML, manifest and blank two-listener sheet are in `data/listening/tts_quality_study*`. Listeners should work independently, declare familiar languages and transcribe/rate before revealing prompts. Rate naturalness (human-like delivery), prosody/pauses and intelligibility separately from critical-term correctness. Use anchors 1 severe problems, 2 substantial problems, 3 noticeable issues but understandable, 4 mostly appropriate/clear with minor issues, 5 natural/appropriate/clear. Mark inability to judge and preserve disagreements. Average within clip before reporting across clips; report ratings/listener/language/missingness counts and avoid population MOS claims.

Guarded non-transactional support only. Confirm critical amounts, identifiers, names, actions and negation. A small held-out ASR check is now measured separately; held-out TTS correctness, broader language-qualified listening, handset/Exotel tests and extended load remain unvalidated. The default report's audio, original references and human marks are available in the release and reproducible by the single runner.

## Fresh Timbre follow-up — 15 November

The extension has 65 initial cases plus eight named diagnostic rechecks of four initial HTTP-200 header-only failures, at 24/48 kHz. Three English texts are each repeated three times per model. Latency ends at full response receipt. Models use different catalog voices; ordering is fixed and regional/load/cold-state effects are uncontrolled. Six new SSE traces are reconstructed independently using integer PCM sample positions and compared separately from the older 14 traces.

Blind audio-model assessment receives audio without reference text, model/version or intended cue; pair assessment randomizes A/B order while disclosing the requested comparison. Cached responses preserve model/version, audio SHA-256, prompt fingerprint, token usage and provisional-assessor provenance. Six empty responses have no audio to rate. Existing human scores are never overwritten. Two planted/unchanged controls show the model misses a known 900 ms initial gap; it cannot certify silence timing. Naturalness/prosody/cue judgments remain one model’s exploratory screen, not human MOS. See TIMBRE_FOLLOWUP.md for per-case results, rubric, failed requests and full limitations.

## Report 4 controlled and held-out methods

The frozen seed-4104 protocol uses identical 61/396/930-character strings, matching language, speed and mono PCM16/24 kHz. Two REST warm-ups are excluded; five successful trials/cell are measured sequentially in randomized within-block version order. Separate short-prompt WS trials use established sockets: two cold warm-ups excluded, five warm trials/version. No p95 or provider compute/queue attribution is inferred. Median RTF aggregates individual dispatch-to-body time / decoded duration ratios. Different Tarika/Kaveri voices remain a limitation.

The attempt ledger includes six prior SSE HTTP requests as well as REST, deduplicates validation events by request ID and distinguishes a retry from an explicit recheck. Positive PCM is required; saved SSE PCM bytes are not falsely labeled wire-response size. Fixed 0/50/100/200/500/1000 ms prebuffers and 1/10/20 ms tolerances are replayed on 32 saved traces (576 conditions). Cumulative received audio/buffer levels are observable; provider generation-stage timestamps are not.

Generic keyterms and rewrite rules are frozen before new predictions. Fifteen unused public MInDS-14 banking recordings use original transcriptions with source/hash checks, supported en-IN API hints and en-US source-locale limits. They are not merged into the original ASR benchmark. Target/critical lexical diagnostics do not certify full semantic correctness. New naturalness and rewrite marks remain uncollected; opaque randomized listener IDs/clip labels and separate mapping preserve a practical blinded review procedure. One missing v3.0 quality clip leaves 15 matched neutral prompt pairs; exclude its unmatched v2.5 counterpart from model comparisons.

## Final submission clarification

**Streaming provenance:** 32 traces = 14 earlier N8 SSE + 6 later SSE + 10 measured warm WebSocket + 2 cold WebSocket warm-ups. The additional IDs are `R4-WARM-WS-3-1` and `R4-WARM-WS-25-1`. Cold warm-ups are retained in the 576 offline buffer conditions and excluded from warm TTFA medians. See [the full provenance inventory](STREAMING_TRACE_PROVENANCE.md).

**Human validation status:** the new three-listener quality panel and ten held-out TTS rewrite pairs are **prepared, awaiting scores**. Their audio generation is complete; their human evaluations are not completed tests and contribute no new quality/correctness results. Existing historical human marks and the completed held-out ASR experiment are separate.

From this `evidence/` repository directory, run `python run_evaluation.py --mode replay --part all --reports`. The final executed submission notebook is [../final_evaluation.ipynb](../final_evaluation.ipynb); start there when reviewing all completed public stages and their retained outputs.
