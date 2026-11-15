# Gnani Prisma and Timbre speech evaluation

Read **report.pdf**, the two-page assignment assessment. **next_stages_report.pdf** provides source-reference, human-listening and playback-verification details. Tests: 13–15 November 2026.

## Reproduce both assignment parts

Tested on Python 3.14 / Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe run_evaluation.py --mode replay --part all --reports
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The default **submission** profile uses public ASR audio with original dataset transcripts and explicit human TTS judgment rows. It makes no API calls. `--part asr` or `--part tts` selects one part; `--output-dir` changes the output directory. Report generation requires `--part all`. NumPy accelerates the TTS PCM diagnostics. Setup ranges are in `requirements.txt`; exact tested versions are in `requirements-lock.txt`.

The headline benchmark is reproducible from released audio, transcripts, saved API responses and human marks. Private recordings and their transcript/score records are excluded from the public release. Private recordings do not contribute to its results. `gnani_submission.ipynb` is a single notebook covering both assignment parts through the same runner. The original exploratory notebooks and restricted tests remain in the working archive and are excluded from the public ZIP. The released benchmark needs no restricted inputs.

## Results and evidence

| Output | Purpose |
|---|---|
| `results/submission/asr_results.csv` | 370 public inputs: 226 baseline (221 speech + 5 controls), 120 follow-up, 24 extension |
| `results/submission/tts_results.csv` | 110 human-scored targets across 66 clips; other targets do not enter headline correctness |
| `results/submission/tts_human_quality_ratings.csv` | Four unique existing human clip ratings, deduplicated from seven target rows |
| `results/submission/tts_audio_quality.csv` | Decode, level and internal-pause diagnostics for all 164 generated clips |
| `results/submission/paired_model_keyterm_streaming.csv` | Identical-input ASR model/keyterm/stream comparisons using source references |
| `results/submission/tts_human_rewrite_pairs.csv` | Nine complete human-reviewed raw/rewrite pairs |
| `results/submission/evidence_manifest.csv`, `cohort_overlap.csv` | Source, speaker, parent, hash and cohort provenance |
| `results/submission/summary.json` | Corpus-weighted scores, verified latency/RTF and reconciled denominators |
| `results/submission/*latency*trace.csv` | Per-request/run IDs, decoded PCM duration, cold/warm boundaries and recomputed timers |
| `results/playback_validation/buffer_sensitivity.csv`, `buffer_sensitivity_summary.csv` | 168 conditions: 14 streams ? 4 prebuffers ? 3 reporting tolerances |
| `results/playback_validation/index.html` | Play immediate/delayed reconstructed playback for all 14 streaming traces |
| `results/playback_validation/playback_validation.csv`, `playback_gaps.csv` | Byte/sample checks and exact underrun intervals |
| `results/playback_validation/*__immediate.wav`, `*__delayed.wav` | 28 audio reconstructions with measured startup and network gaps |
| `results/submission/request_attempts.csv`, `streaming_chunk_timestamps.csv` | Saved request/event diagnostics and explicit unrecorded fields |

The submission baseline uses 309 word edits / 1,630 reference words: **18.96% WER** (raw 24.18%). Follow-up: **21.11%**; public extension: **19.28%**. Cohorts use different utterances and share some speakers; their percentages are not paired model-change estimates. The 24 extension inputs are exactly the 12 finance questions and 12 technical Hindi-English clips.

Human TTS correctness: baseline **57/62 (91.94%)**, targeted follow-up **35/48 (72.92%)**. Suspected failures were deliberately selected, so these are diagnostic subset scores. Existing human naturalness mean/median is **4.50/5**, prosody **5.00/5**, across four clips and one listener; this is not broad-language or population MOS evidence. All 164 clips also receive objective audio diagnostics, which do not substitute for perceptual judgment.

Playback verification independently checks PCM byte/sample consistency and reconstructs audible underruns: **12/12 v3.0** streams stall after first audio; **0/2 v2.5** controls do. Exact extra wait is **0.845–3.911 s**. The maximum correction to the earlier rounded-duration estimate is 1.18 ms. Retrospective delayed starts use future arrivals and are not a universal live buffer recommendation.

## Review boundaries

[Source attribution](DATASETS.md), [methods and listening rubric](METHODS.md), [testing stages](TESTING_STAGES.md), [changes](IMPROVEMENTS.md). Public source notices and hashes are retained. Credentials, private raw audio/transcripts, call-session artifacts, caches, backups and personal spending notes are excluded. Old private-archive summaries, charts and notebooks are excluded; the reported scope is defined by `results/submission/summary.json`. CSV/JSON records tied to private calls are omitted entirely, including numeric score-only records. No Git history is included.

The optional 12-clip study is prepared at `data/listening/tts_quality_study.html`, with a blank response template. More independent language-qualified ratings, held-out TTS correctness ratings, real handset/Exotel validation and extended load remain future stages. The 15 November follow-up adds 73 TTS cases across 74 HTTP attempts, preserving six header-only failures and one expected rejection; replay itself makes no paid calls. Pinned dependencies installed successfully in a fresh isolated Python 3.14.4 environment; `pip check` passed. See VERIFICATION.md for the release replay checks.

For optional new collection, configure credentials from `.env.example` and explicitly select cases, for example `python scripts/run_batch.py --asr CL-EN-01 --tts T31 --run-tag new_validation --live`. This is separate from the credit-free replay. New generated TTS audio needs new judgments before replacing published scores.

## Fresh Timbre follow-up

Read [TIMBRE_FOLLOWUP.md](TIMBRE_FOLLOWUP.md) for non-streaming response waits, six fresh SSE controls, all 13 documented v3.0 tags, Hindi variants, v2.5 stripping controls, pacing and numeric inputs. Open `results/timbre_followup/index.html` for the 66 successful new clips and reconstructed playback. This is separate from the original 164-clip cohort.

New audio-model ratings and cue comparisons are provisional and separate from the human scores. The model missed a planted silence control; waveform/chunk measurements provide timing evidence. The standard replay rebuilds the new summaries and both PDFs without API calls. Live collection remains opt-in through `scripts/timbre_followup.py --live --judge-live` and reuses successful caches; original failed trials are retained.


## Side-by-side listening comparison

Open [timbre_comparison.html](timbre_comparison.html) in a modern browser. It embeds 18 saved clips for nine comparisons: short/medium/long streaming playback, median-latency REST audio and neutral/whisper/excited delivery. The file works offline and can be shared independently. REST response-wait replay is a timed demonstration using the selected run; streaming audio retains independently reconstructed startup and network gaps. Different model-specific voices limit general quality claims.

Rebuild without API calls: `python scripts/build_timbre_comparison.py`. Audio source paths, SHA-256 hashes and selection rules are recorded in results/timbre_followup/comparison_manifest.json.

## Report 4 final validation

Read [REPORT4_IMPLEMENTATION.md](REPORT4_IMPLEMENTATION.md) for the verified action matrix and final five-repeat REST/RTF, separate warm WebSocket, attempt reconciliation and 1000 ms buffer findings. Open `results/report4/index.html` for plots/tables/playback. A separate 15-clip frozen-vocabulary banking check is scored without changing baseline WER. The new blinded listening and ten held-out rewrite pairs are audio-ready with zero new human scores; open `results/report4_quality/listening.html` and `rewrites.html`. The standard replay rebuilds these results without API access. The portable comparison now selects the controlled five-repeat REST median runs; its streaming tab retains the earlier six SSE traces.


## Final REST sample-count clarification

The controlled comparison uses one text per short/medium/long group: 2 models × 3 texts × 5 successful repeats = **30 measured requests**, plus **two excluded warm-ups** (32 controlled REST requests total). The **60 completed REST files** refer to a separate earlier waveform-check set: **18 earlier timing runs + 42 functionality/configuration outputs**. These earlier files are not pooled into the controlled timing medians. Per-case memberships and source IDs are in results/submission/rest_cohort_membership.csv; the sets share no case IDs.

## Final submission clarification

**Streaming provenance:** 32 traces = 14 earlier N8 SSE + 6 later SSE + 10 measured warm WebSocket + 2 cold WebSocket warm-ups. The additional IDs are `R4-WARM-WS-3-1` and `R4-WARM-WS-25-1`. Cold warm-ups are retained in the 576 offline buffer conditions and excluded from warm TTFA medians. See [the full provenance inventory](STREAMING_TRACE_PROVENANCE.md).

**Human validation status:** the new three-listener quality panel and ten held-out TTS rewrite pairs are **prepared, awaiting scores**. Their audio generation is complete; their human evaluations are not completed tests and contribute no new quality/correctness results. Existing historical human marks and the completed held-out ASR experiment are separate.

From this `evidence/` repository directory, run `python run_evaluation.py --mode replay --part all --reports`. The final executed submission notebook is [../final_evaluation.ipynb](../final_evaluation.ipynb); start there when reviewing all completed public stages and their retained outputs.
