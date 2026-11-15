# Gnani speech evaluation — final submission

Start with **[submission.html](submission.html)** in Chrome, Edge or Firefox. It is an offline, detailed evidence walkthrough with playable public clips, ASR reference/transcript differences, TTS prompts and human target marks, matched comparisons, recorded streaming gaps, complete searchable clip records and source exports.

The streaming section shows **when every chunk was received and when it plays** on a shared request-dispatch clock. Play or seek the arrival-timed audio to follow the cursor, current chunk, next arrival and queued audio. Expand the per-chunk table for exact receive/start/end times, queue waits and empty-buffer gaps. Fixed-buffer comparisons show the same timeline. [Download the derived receive/play ledger](assets/stream_playout_timeline.csv).

The **“HTTP success is not always usable audio”** section lists all seven HTTP-200/header-only WAV responses and lets you inspect each exact prompt, configuration and original failed file. Notebook section 18 covers these results: cells **38–39** counting all cells from 1; the executed results are in **In [19]**. All seven files are 44 bytes and contain zero decoded audio samples.

## Main deliverables

| File | What it contains |
|---|---|
| [report.pdf](report.pdf) | Corrected two-page interview-assignment assessment: results, observed failures, prioritized improvements and limits |
| [final_evaluation.ipynb](final_evaluation.ipynb) | The complete public test walkthrough, from setup through final conclusions, with every code cell executed and its output retained |
| [submission.html](submission.html) | Detailed audio/transcript/prompt gallery and searchable public catalog; one clip plays at a time |
| [HTML_PLAN.md](HTML_PLAN.md) | The page structure and verification plan recorded before building the HTML |
| [build_submission.py](build_submission.py) | Rebuilds the HTML and catalog from bundled evidence, without API calls |
| [submission_manifest.json](submission_manifest.json) | SHA-256 hashes of the final delivered files |

Keep the **whole folder** together when sharing. `evidence/` contains the privacy-filtered source, public audio, saved API responses, CSVs, licenses and supporting reports. `media/` contains browser-friendly WAVs where header repair/codec decoding was necessary; decoded PCM is verified unchanged. `assets/` contains the complete machine-readable catalog, source/display audio hashes, page template and verification output.

Verified delivery: **53 notebook cells, 26 executed code cells, 74 passing implementation checks, a two-page report, 1,341 catalog records and 984 checked audio mappings.** The browser checks cover playback, exclusive audio, comparison switches, search, filters, pagination, case details and mobile layout. Verification records are in [submission_verification.json](assets/submission_verification.json), [notebook_execution.json](assets/notebook_execution.json) and [browser_validation.json](assets/browser_validation.json). Root and evidence manifests describe the final delivered bytes; replaying or rebuilding derived files can change their hashes.

## P0: REST sample-count clarification

There was **one input text per prompt-length group**, not two.

| Set | Definition | Count | Used for |
|---|---|---:|---|
| Latest controlled REST measurements | 2 models × 3 distinct texts × 5 successful repeats | **30** | Latest latency, decoded duration and client RTF medians/ranges |
| Controlled REST warm-ups | One short request per model, excluded from measurements | **2** | Connection/model warm-up; 32 controlled REST requests total |
| Earlier completed REST waveform files | 18 earlier timing runs + 42 functionality/configuration outputs | **60** | Earlier waveform/early-gap inspection; not pooled into the controlled timing cohort |
| Earlier SSE outputs | Separate streaming outputs from that earlier follow-up | **6** | Streaming timing/playback inspection; excluded from the 60 REST files |

The 18 earlier timing runs used **three repeats per model/text**. The remaining 42 successful earlier REST outputs cover tags, neutral delivery, invalid tags, speed, normalization, sample rates and rechecks. The earlier and controlled sets share **zero case IDs**. Their prompt text may repeat; requests and texts are different denominators. The original single-model six-prompt/five-repeat timing study is another historical cohort, explicitly labeled in the notebook and HTML.

Exact per-case membership: [rest_cohort_membership.csv](evidence/results/submission/rest_cohort_membership.csv). Machine-checked definitions: [rest_count_reconciliation.json](evidence/results/submission/rest_count_reconciliation.json).

## What the completed tests establish

- Primary public ASR: 226 baseline inputs (221 speech + five no-speech), 120 follow-up and 24 extension inputs. Original source-reference WER: **18.96%, 21.11% and 19.28%**. Cohorts differ and share some speakers.
- Original TTS: **164 generated clips**. Selected human-scored subsets: **57/62** baseline targets and **35/48** targeted targets correct. These failure-enriched subset scores are not population accuracy.
- Controlled REST: five successful repeats/model/text. Short/medium/long medians are **3.44/6.50/11.75 s for v3.0**, **0.77/1.18/2.56 s for v2.5**. These are complete-body waits, not TTFA or speech duration. Voices differ.
- Separate warm short-prompt WS: median TTFA **813 ms vs 161 ms**, five runs each. V3.0 immediate playback underruns in 5/5; v2.5 in 0/5. These and earlier stream cohorts are separate saved-trace analyses, not handset tests.
- Buffer sensitivity: **32 traces × six prebuffers × three tolerances = 576 conditions**. A 1,000 ms prebuffer still leaves some v3.0 underruns and adds startup delay.
- Held-out ASR: 15 unused public banking recordings under a frozen vocabulary, WER **19.33% → 18.67%**. One improved, 14 unchanged. Target coverage is only “account”; bank-name/acronym gains remain untested. These are 8 kHz US-English recordings with unknown speaker identity.
- All 13 documented v3.0 expression tags were exercised; superior perceived quality was not established. A one-request all-tag demo is included. Audio-model observations are provisional and the evaluator missed a planted gap.

The HTML and notebook also retain the public noise/codec/pause comparisons, Prisma versions and output-format explorations, keyterm experiment selected from errors, original timing/voice/round-trip probes, critical TTS failures, scored raw/rewrite pairs, HTTP/empty-audio/retry outcomes, request-concurrency and short-soak outputs.

## What remains unperformed

The new independent quality panel and ten held-out TTS rewrite pairs are **audio-ready but unscored**. Their blank response sheets are not evidence. The prepared study has 33 valid quality outputs (15 complete neutral model pairs plus extra material); one v3.0 request was empty. No human scores were invented.

Open the [independent listening study](evidence/results/report4_quality/listening.html) and [new raw/rewrite pairs](evidence/results/report4_quality/rewrites.html) to review them. Live handset/Exotel tests, real interruption/late-audio cleanup and extended-load production validation remain unestablished. Source-reference uncertainty and different model-specific voices limit generalization. Private earlier call material is excluded and never required to reproduce this release.

## Configuration and Git exclusions

[.gitignore](.gitignore) and [.env.example](.env.example) are provided at the submission root; the supporting repository also retains `evidence/.gitignore` and `evidence/.env.example`. The templates contain blank keys and default live mode to off. Offline report/notebook replay needs no credentials.

For optional live collection only, copy the root template to `evidence/.env`, because the bundled clients read that path. Populate keys locally and use the documented explicit live flags. Git excludes local credentials, environments and caches while retaining the public evidence, audio and executed notebook outputs.

## Replay from start to end

Tested with Python 3.14.4 on Windows. No model credentials are required and no paid API calls occur during replay.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r evidence\requirements-lock.txt
.\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace final_evaluation.ipynb --ExecutePreprocessor.timeout=600
.\.venv\Scripts\python.exe build_submission.py
```

Start Jupyter in this `GA_Submission` directory. The first cell replays the published entry point in `evidence/`; subsequent sections display every public test stage with complete output tables, selected embedded listening examples and all source links. Full implementation checks execute at the end. Synthetic call/recording fixtures in those checks do not imply real telephone experiments.

Direct core replay from this folder: `python evidence/run_evaluation.py --mode replay --part all --reports`. Alternatively, change into `evidence/` and run `python run_evaluation.py --mode replay --part all --reports`. The notebook refreshes the root report from the replayed two-page PDF.

See [dataset attribution](evidence/DATASETS.md), [methods](evidence/METHODS.md), [Report 4 details](evidence/REPORT4_IMPLEMENTATION.md), and [versioned earlier follow-up](evidence/TIMBRE_FOLLOWUP.md). Final packaging excludes credentials, private call audio/transcripts, personal spending notes, internal backups and restricted exploratory notebooks. The release preserves public frozen protocol/API-result bytes when no privacy transformation is necessary.

## Final submission clarification

The **32 streaming traces** are **14 earlier N8 SSE + 6 later SSE + 10 measured warm WebSocket + 2 cold WebSocket warm-ups**. The additional warm-up IDs are `R4-WARM-WS-3-1` and `R4-WARM-WS-25-1`; both are retained in the offline buffer inventory but excluded from the warm TTFA medians. [Full provenance, all request IDs and source links](evidence/STREAMING_TRACE_PROVENANCE.md).

The new three-listener panel and ten held-out rewrite pairs remain **future human validation**, with no completed scores claimed. Repository replay and referenced Markdown files are checked in [repository_verification.json](assets/repository_verification.json); the documented offline runner reproduces the headline metrics without new API calls.
