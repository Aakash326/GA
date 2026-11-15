# Submission verification ? 15 November 2026

## Setup and entry points

Pinned dependencies were installed from requirements-lock.txt into a fresh isolated Python 3.14.4 environment on Windows. `pip check` reported no broken requirements. The single public-evidence notebook executed in that environment with API keys removed and live mode disabled. The standard command is:

```powershell
python run_evaluation.py --mode replay --part all --reports
python -m unittest discover -s tests -v
```

`gnani_submission.ipynb` runs the same ASR/TTS pipeline and displays the report evidence. No speech API credentials or new API calls are required. Four restricted exploratory-archive tests and older notebooks remain local and are excluded from the public package.

## Reconciled report values

| Evidence | Verified value / trace |
|---|---|
| Public ASR counts | 226 baseline = 221 speech + five controls; 120 follow-up; 24 extension; baseline language counts sum to 221 |
| Custom corpus WER | Baseline 309/1,630 = 18.96%; follow-up 186/881 = 21.11%; extension 48/249 = 19.28% |
| Empty controls | Five controls excluded from speech WER/CER; no false transcription in this set |
| TTS selected scored subsets | Baseline 38 clips / 62 targets: 57 correct, four wrong, one ambiguous; follow-up 28 / 48: 35 correct, 12 wrong, one ambiguous |
| Supplementary marks | 74/89 marked targets overlap the final human scores; 15 blanks add no marks |
| Exploratory perceptual ratings | Four clips, one listener: naturalness mean/median 4.50/5; prosody 5.00/5; seven repeated target rows deduplicated |
| ASR REST latency | 192.1 ms median over 221 public speech clips, matched to saved attempt IDs |
| TTS REST latency / RTF | 98 baseline prompts: 1,492.25 ms median; median per-clip RTF 0.372277 from actual decoded PCM duration |
| Cold/warm timing | Thirty short-prompt runs, five per model/transport/connection group; handshake added only to cold per-run totals before median |
| ASR streaming latency | Eighteen paired benchmark clips; final transcript median 262.6 ms after clip end, displayed as 263 ms; separate pilot excluded |
| PCM playback | All 14 chunk-byte totals match decoded audio frames; 12/12 tested v3.0 traces underrun, 0/2 v2.5 controls |
| Buffer sensitivity | 168 stream/condition rows; 0/50/100/200 ms startup buffering and 1/10/20 ms reporting tolerance preserve the finding in these tested configurations |
| Account stress / short soak | First eight-request round: TTS 2/8 successes, ASR 8/8 with six retried; short soak 30/30 |

Traces: results/submission/asr_results.csv, tts_results.csv, *latency*trace.csv, request_attempts.csv, paired experiment exports and results/playback_validation/*.csv. Playback HTML includes 28 immediate/delayed reconstruction WAVs. Detailed 50-clip selection/overlap and scoring provenance remain in METHODS.md and source judgment rows.

## Release integrity

The public ZIP excludes private raw recordings, transcripts, call-session artifacts, private score-only records, credentials, caches, backups, stale private-archive summaries/charts, older notebooks and Git history. CSV/JSON call records are omitted entirely. Known secret values are checked without printing them. SHA-256 hashes describe the released/transformed bytes, and CRC/hash verification is performed during packaging.

The public entry point is checked from a separately extracted ZIP in the fresh environment. This release makes no claim that exploratory files outside the submitted scope are needed for reproduction.

## Interpretation limits retained

TTS percentages describe selected scored targets, not all 164 generated clips or population accuracy. Four single-listener perceptual ratings are exploratory, not reliable MOS. Twelve v3.0 and two v2.5 simulation controls do not establish model superiority or handset reliability. Future-aware delayed replay is diagnostic. Broader independent listening, scored held-out TTS rewrites, online jitter buffers/interruption handling, handset tests and extended load remain future validations; Report 4 separately records the held-out ASR check.

## Fresh Timbre follow-up — 15 November

The extension contains 73 cases across 74 HTTP attempts: 66 valid audio clips, six header-only HTTP-200 failures and one expected tag-only HTTP 400; one HTTP 500 recovered on retry. Original 370 public ASR inputs and original human content/perceptual scores are unchanged. Canonical listening WAVs preserve decoded PCM while repairing placeholder lengths. Six fresh streaming reconstructions independently match chunk bytes to PCM samples. Blind and paired model judgments preserve real audio hashes and separate provisional provenance. The positive silence control failed model detection and is explicitly reported. New regression tests cover planted gap discrimination, PCM preservation, cache hashes/provenance and network-free replay; release checks are recorded after packaging below.


### Follow-up release checks

The final extracted submission passed 64 public tests in the fresh Python 3.14.4 environment. Both report rebuilds and the complete public notebook ran with API credentials removed and live mode disabled. Both PDFs contain exactly two pages. The executed notebook is included. The unchanged original human scores and source-reference ASR scores reconciled successfully.

Fresh evidence: 73 cases across 74 HTTP attempts (72 HTTP 200, one HTTP 500 recovered on retry, one expected HTTP 400). There are 66 valid clips and six empty HTTP-200 WAVs. The 103 cached model responses comprise 66 blind assessments, 29 pair comparisons and eight playback/control assessments. Cue/timing limitations are disclosed. Replay makes zero new API calls. The final ZIP receives CRC and SHA-256 verification and the existing private-audio/credential exclusions.


### Listening comparison HTML

All 18 embedded WAV hashes match their saved sources. Headless Chrome decoded every audio asset and verified sequential playback, all nine selectable pairs, REST timing replay and cancellation, and a 390 px mobile layout without horizontal overflow. JavaScript syntax validation passed. The page is standalone, needs no API calls, and makes no new perceptual pass-rate claims.


## Report 4 final release gate

The exact extracted submission passed 73 public tests in the existing clean Python 3.14.4 environment. The standard replay rebuilt all report figures, and the complete notebook executed with API credentials removed and live mode disabled. Both PDFs are exactly two pages. The executed notebook is included. Original source-reference ASR and explicit human TTS scores remain unchanged.

The controlled extension has 30 measured REST successes, two excluded REST warm-ups, ten measured warm WS successes and two excluded cold WS warm-ups. The attempt ledger explicitly includes the prior six SSE HTTP requests and distinguishes 73 cases, 74 attempts, 66 valid outputs, six empty outputs, one HTTP 500 retry and one expected HTTP 400. New prepared quality/rewrite audio has 54 cases, 53 valid outputs and one empty response. No new human quality or held-out rewrite marks are claimed.

All 32 stream byte/sample totals reconcile, with 576 fixed-buffer/tolerance replay conditions. Fifteen source-hashed held-out ASR clips yield 29/150 versus 28/150 word edits under the frozen vocabulary; target coverage is only “account,” and source speech is 8 kHz US English with unknown speaker identities.

Headless Chrome verified all 18 embedded comparison clips, sequential playback, response-wait cancellation, responsive layout, anonymous listener selection, native audio, CSV export/validation and the controlled plot/playback page. Browser fixture ratings were kept outside the project and never imported into actual listening sheets. Public JSON whose privacy transformation is a no-op is preserved byte-for-byte, protecting frozen policy/request-result hashes; mixed private JSON still undergoes redaction. Two added regression checks cover both behaviors. CRC, release SHA-256, private-record exclusions and credential checks run again during final packaging.

## Final submission clarification

**Streaming provenance:** 32 traces = 14 earlier N8 SSE + 6 later SSE + 10 measured warm WebSocket + 2 cold WebSocket warm-ups. The additional IDs are `R4-WARM-WS-3-1` and `R4-WARM-WS-25-1`. Cold warm-ups are retained in the 576 offline buffer conditions and excluded from warm TTFA medians. See [the full provenance inventory](STREAMING_TRACE_PROVENANCE.md).

**Human validation status:** the new three-listener quality panel and ten held-out TTS rewrite pairs are **prepared, awaiting scores**. Their audio generation is complete; their human evaluations are not completed tests and contribute no new quality/correctness results. Existing historical human marks and the completed held-out ASR experiment are separate.

From this `evidence/` repository directory, run `python run_evaluation.py --mode replay --part all --reports`. The final executed submission notebook is [../final_evaluation.ipynb](../final_evaluation.ipynb); start there when reviewing all completed public stages and their retained outputs.

Current delivery checks supersede the explicitly dated earlier 64/73-test checkpoints above: 74 implementation tests pass. See [repository verification](../assets/repository_verification.json) and [final package checks](../assets/submission_verification.json) for the current release.
