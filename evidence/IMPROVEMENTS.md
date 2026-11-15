# Final report changes ? 15 November 2026

- Reported ASR now uses public audio only: 226 baseline inputs (221 speech + five controls), 120 follow-up and 24 extension inputs. Original dataset transcripts are used consistently. Baseline source-reference WER is 309/1,630 = 18.96%; changed scores reflect the scope/reference policy, not a new model run.
- TTS headline correctness uses human marks only: baseline 57/62 across 38 clips; follow-up 35/48 across 28 clips. Unmarked targets do not enter the scores. The 74/89 selected review marks overlap these totals.
- Added the previously unreported existing naturalness/prosody results: four unique clips, one listener, naturalness mean/median 4.50/5 and prosody 5.00/5. Seven target rows are deduplicated to four clip ratings; coverage limits are explicit.
- Added objective PCM decode/level/pause diagnostics for all 164 generated clips. These do not replace perceptual judgments. All 164 REST WAVs have placeholder length fields; the checker uses actual PCM sample counts and bounded reads.
- Independently validated all 14 playback traces against exact PCM sample counts and rendered 28 immediate/delayed playback WAVs. Stalls: 12/12 v3.0, 0/2 v2.5. Exact extra wait 0.845?3.911 s; largest prior duration-rounding difference 1.18 ms.
- Recomputed paired ASR model/keyterm/stream and acoustic comparisons against the same source references. The human-only rewrite subset has nine complete pairs: eight fixed, one failed both; selection bias is disclosed.
- The default single runner rebuilds the submitted benchmark from available public inputs, saved responses and human judgment rows. Private recordings do not contribute to headline results. The reported benchmark is fully replayable from available public inputs; content judgments come from explicit human marks.
- Both reports remain two pages. Source notices, hashes, raw evidence and separate exploratory provenance are preserved. Private raw recordings/transcripts, credentials, personal spending records and notebook outputs are excluded from the ZIP.

No new paid calls or invented human ratings. Broader independent language listening, new held-out mitigations, live handset validation and extended load remain future work. See METHODS.md and the playback HTML for exact procedures.

Final checklist corrections: simplified sample-based TTS headings; explicit scored-subset denominators; naturalness labeled exploratory; v2.5 recommendation conditional on larger paired validation. Added 168 buffer/tolerance replays, source-level latency/RTF traces and a fresh isolated dependency installation. Private score-only records and stale archive summaries/charts are excluded from the ZIP. A single public-evidence notebook is included.

## Fresh Timbre follow-up — 15 November

The report now distinguishes non-streaming full-response delay, silence in completed PCM and streaming chunk starvation. New failures include six HTTP-200 responses containing only a 44-byte WAV header; checking status alone is insufficient. Default 48 kHz did not consistently resolve failures. The original failed attempts and explicitly named rechecks are preserved. Expression/pacing controls use the documented model-specific behavior. New audio-model naturalness/prosody ratings remain separate from human marks, and the failed planted-gap control is disclosed. Reproducible per-case findings are in TIMBRE_FOLLOWUP.md and results/timbre_followup/.

## Report 4 final implementation

Added a five-repeat controlled REST duration/RTF study, separate warm WS TTFA, disjoint REST/SSE attempt audit, explicit retry/recheck links, positive-PCM validation, six-buffer/three-tolerance playback tradeoffs, and a scored 15-clip frozen-vocabulary banking experiment. Added an audio-ready blinded quality panel and ten held-out TTS rewrite pairs, retaining one new empty response and leaving new human marks blank. Updated the two-page main/supplementary reports and portable comparison to use versioned, separate evidence. Architectural latency cause and superior perceived quality remain unestablished. Detailed status: REPORT4_IMPLEMENTATION.md.
