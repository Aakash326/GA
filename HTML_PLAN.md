# Detailed submission HTML plan

Plan recorded before building the final HTML. Target: `GA_Submission/submission.html`.

## 1. Entry point and evidence scope

Show the guarded-pilot decision, links to the two-page report and executed notebook, and an explicit cohort diagram/table. Explain that the latest controlled REST benchmark has one text per short/medium/long group: 2 versions × 3 texts × 5 repeats = 30 measured requests, plus two excluded warm-ups. The earlier 60-file REST waveform set comprises 18 earlier timing runs and 42 valid functionality/configuration outputs, not 60 latest controlled measurements. Keep primary human TTS scores, version/functionality follow-up and unscored listening material separate.

## 2. Test-stage navigation

Use an offline responsive page with persistent section navigation:

1. Scope, datasets, definitions and count reconciliation.
2. ASR results, language/category breakdowns and no-speech controls.
3. ASR failure gallery: original audio, frozen reference, actual hypothesis and word-edit highlights.
4. ASR paired tests: noise/codec/pause conditions, versions, streaming, error-selected hints and held-out hints.
5. TTS critical readings: exact submitted prompt, expected target and human correct/wrong/ambiguous mark.
6. Matched v3.0/v2.5 completed REST audio with five-run timing ranges, decoded duration and client RTF.
7. Streaming playback: actual concatenated speech versus arrival-timed reconstruction, gap intervals and fixed-buffer tradeoff.
8. Raw/rewrite comparisons: nine scored human pairs; ten new unscored pairs clearly labeled.
9. All 13 expression tags, including unsuccessful requests and the one-request all-tags demonstration.
10. Reliability, request outcomes, concurrency, short soak and remaining validation.
11. Searchable public audio/transcript/prompt catalog and source exports.

## 3. Listening interaction

Use native audio players with one clip playing at a time, visible case IDs, model/voice/language and controls to reset playback. Put the matched text next to comparison players. REST files play complete saved audio without artificial response-wait silence; response-wait simulation is explicitly labeled. Streaming reconstruction includes measured startup/gap zeros and is explicitly distinguished from native audio and real handset recordings. Use actual human target marks for pronunciation failures; identify any machine transcript or quality judgment as provisional. Do not invent full human transcripts for TTS when only target judgments exist.

## 4. Full catalog and source traceability

Provide search, language/model/cohort/type filters and pagination for all included public benchmark inputs and TTS outputs. Show actual reference/hypothesis or submitted TTS prompt and available judgments. Include links to complete CSV tables rather than presenting selected examples as population accuracy. Reuse the privacy-filtered evidence archive. Copy/remux only when finite WAV headers are needed, verifying decoded PCM is unchanged. Record source and display-file hashes.

## 5. Notebook alignment

The final notebook follows the same test stages from setup/data integrity through metrics, ASR/TTS results, optional public experiments, latency/reliability, controlled follow-up and held-out checks. Each section explains the question, inputs, method, denominator, output and limits. Execute every code cell without API credentials, retain outputs, and display full per-clip tables and selected playable examples. Live telephone/private-call experiments remain unperformed or excluded as appropriate; they are not represented as completed public tests.

## 6. Delivery layout

Root files: `README.md`, `report.pdf`, `final_evaluation.ipynb`, `submission.html`, this `HTML_PLAN.md`, a reproducible `build_submission.py` and `submission_manifest.json`. Supporting public code/data/results live under `evidence/`; browser-friendly audio and any supplementary charts live under `media/` and `assets/`. All page resources are local; no API keys, private call recordings/transcripts, personal spending notes or remote dependencies are included.

## 7. Verification before delivery

Check counts against source rows and IDs; verify all linked audio exists and decodes; compare remuxed PCM hashes; execute the full public tests and the entire notebook; verify the two-page report; inspect desktop/mobile HTML; exercise search/filter/pagination and playback; scan for secrets/private IDs; generate final release hashes and an optional shareable ZIP. New independent listening/rewrite scores and live handset/extended-load validation remain explicitly pending.
