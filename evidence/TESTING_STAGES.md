# Evaluation stages

1. Prepare consented/licensed audio, source identifiers, hashes, language hints and transcript provenance. Freeze source selection before model scoring.
2. Implement and check Unicode normalization and custom Levenshtein WER/CER. Keep raw and normalized denominators consistent.
3. Evaluate Prisma on baseline and follow-up cohorts. Keep paired acoustic transformations linked to their source; report corpus and per-language metrics.
4. Evaluate Timbre against predefined critical targets. Headline scores use explicit human marks only; ambiguous targets fail strict correctness. Unmarked targets do not add human scores.
5. Measure REST latency/RTF, streaming arrival/playback behavior, cold versus warm connections, retries, concurrency and a short soak.
6. Test selected mitigations: keyterms, output format, model selection and explicit TTS rewrites. Keep error-selected or oracle-hint experiments distinct from generalization claims.
7. Freeze original dataset references for submitted ASR scoring. Preserve uncertainty and separate reference variants in supporting evidence; do not replace source text in the reported benchmark.
8. Run `python run_evaluation.py --mode replay --part all --reports`, inspect the exported provenance/diagnostic tables, run regression/integrity checks and verify submission file hashes.

The saved notebooks and reports document completed experiments. Proposed rollout checks, independent native-listener validation and real telephone-network tests are not represented as completed evidence.

The optional next listening stage is prepared as 12 existing clips with a blank response template in `data/listening/tts_quality_study*`. Instructions and scoring anchors are in `METHODS.md`; no new ratings have been collected. The later Report-4 section records the completed held-out ASR check; independent TTS correctness marks remain pending. The default runner rebuilds the complete reported benchmark from released public audio/source transcripts and human marks. Four actual existing human naturalness ratings are reported separately from the prepared study. Independent PCM-sample playback reconstruction is included for all 14 streaming traces.

## Fresh Timbre follow-up — 15 November

Completed: official guidance check; 73 cases across 74 HTTP attempts covering REST/SSE, tags, invalid/tag-only input, English/Hindi, speed, 24/48 kHz, numeric raw/rewrite and eight diagnostic rechecks; blind audio-model screening; condition-order-hidden cue comparisons; independent PCM playback reconstruction and two judge controls. Successful audio, failures and judgments are separate from the original cohorts.

Next: native-speaker confirmation of cues/critical readings; broader held-out prompts/voices; a prospective online jitter-buffer/interruption test; handset/Exotel validation if required; extended-load testing. Do not treat prepared templates or reconstructed playback as completed human/handset studies. Replay runs via the standard command without new paid API access; the optional live follow-up requires explicit flags. Details: TIMBRE_FOLLOWUP.md.

## Report 4 final stages

Completed: controlled five-repeat timing/RTF, separate warm WS timing, attempt-level REST/SSE reconciliation, fixed-buffer replay through 1000 ms, and 15 held-out ASR baseline/keyterm pairs under a frozen vocabulary. Prepared: 33 quality outputs (15 matched neutral pairs plus extra material) with three anonymous listener sheets, and 20 outputs for ten held-out v2.5 raw/rewrite pairs. Independent human scoring remains required; blank templates are not measured results. Live interruption/late-audio cleanup, handset/Exotel and extended-load studies remain separate future validation. Replay and package gates are recorded in VERIFICATION.md.

## Final submission clarification

**Streaming provenance:** 32 traces = 14 earlier N8 SSE + 6 later SSE + 10 measured warm WebSocket + 2 cold WebSocket warm-ups. The additional IDs are `R4-WARM-WS-3-1` and `R4-WARM-WS-25-1`. Cold warm-ups are retained in the 576 offline buffer conditions and excluded from warm TTFA medians. See [the full provenance inventory](STREAMING_TRACE_PROVENANCE.md).

**Human validation status:** the new three-listener quality panel and ten held-out TTS rewrite pairs are **prepared, awaiting scores**. Their audio generation is complete; their human evaluations are not completed tests and contribute no new quality/correctness results. Existing historical human marks and the completed held-out ASR experiment are separate.

From this `evidence/` repository directory, run `python run_evaluation.py --mode replay --part all --reports`. The final executed submission notebook is [../final_evaluation.ipynb](../final_evaluation.ipynb); start there when reviewing all completed public stages and their retained outputs.
