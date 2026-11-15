# Timbre 3.0 and 2.5 follow-up — 15 November 2026

This extension is separate from the original 164 TTS clips and human content scores. All new speech is synthesized from prepared prompts; no private or newly recorded speech is used.

## Gnani guidance checked

- [REST inference](https://docs.gnani.ai/api/TTS/tts-inference): use each model’s own voice catalog, set language explicitly, and choose speed within 0.85–1.15. REST returns complete audio; sending the full input text does not imply immediate playback.
- [Audio tags](https://docs.gnani.ai/api/TTS/tts-audio-tags): 13 case-sensitive inline expression/nonverbal/pacing tags are documented for v3.0. v2.5 strips tags; tag-only input should return 400. Unknown tags should not be spoken.
- [Normalization guide](https://docs.gnani.ai/api/TTS/tts-input-formating): describes automatic number/date/ID normalization. The REST introduction still warns about raw numbers, so numeric behavior was tested rather than assumed.
- [Voices](https://docs.gnani.ai/api/TTS/available-voices) and [transport guidance](https://docs.gnani.ai/api/TTS/tts-websocket): Tarika/Shivani were used for v3.0, Kaveri/Nalini for v2.5; these are different voices. Gnani recommends realtime transport for interactive use and REST for complete files.
- No published note confirming a fix for the previously observed startup gap was found in the checked documentation/changelog. These are public API instructions, not a claim of direct support correspondence.

## Experiment and outcomes

73 planned cases, 73 attempted across 74 HTTP attempts; 66 valid audio clips, 6 HTTP-200 empty WAVs and 1 expected tag-only rejection. One v3.0 speed-control request received HTTP 500 before a successful retry; the failed attempt is retained. The first batch had 65 cases; eight explicitly identified 24/48 kHz rechecks follow four initial header-only failures. These diagnostic counts are not population failure-rate estimates.

Latency uses three sequential repeats for each of three English prompts per model, at 24 kHz. Fixed alternating v3.0/v2.5 ordering; voice, server load, region and connection cold state were not controlled. There are three distinct prompt texts, not nine independent text samples. Tags, Hindi controls, invalid tags, speed extremes, 48 kHz and raw/spoken numeric inputs extend the matrix.

## Non-streaming latency and the sound–silence question

| Model / voice | Length / characters | Runs | Full-response median | Range | Median audio |
|---|---|---:|---:|---:|---:|
| timbre-v3.0 / Tarika | short / 61 | 3 | 5.043 s | 4.195–5.279 s | 3.92 s |
| timbre-v3.0 / Tarika | medium / 396 | 3 | 7.811 s | 5.325–8.386 s | 15.04 s |
| timbre-v3.0 / Tarika | long / 930 | 3 | 17.200 s | 14.634–21.425 s | 51.76 s |
| timbre-v2.5 / Kaveri | short / 61 | 3 | 0.542 s | 0.512–0.714 s | 2.88 s |
| timbre-v2.5 / Kaveri | medium / 396 | 3 | 1.074 s | 1.037–1.089 s | 17.60 s |
| timbre-v2.5 / Kaveri | long / 930 | 3 | 2.750 s | 2.515–3.346 s | 43.20 s |

Yes, v3.0 still has a substantial wait with non-streaming REST in these tests. This interval ends at full-body receipt, before playback; it is not time to first playable audio. Among 60 completed REST clips, the 10 ms RMS detector flagged 0 short initial bursts followed by at least 500 ms of quiet. Sensitivity uses −35/−45/−55 dBFS. This does not certify absence of every perceptual pause. Ordinary phrase pauses and requested `<pauses>` are separate from network underruns.

All text was sent in one request for both REST and SSE. SSE streams the output audio. A completed REST file cannot experience missing network chunks during offline playback; a zero-sample response is a different failure.

| Fresh SSE case | First audio | Underruns after start | Total starvation |
|---|---:|---:|---:|
| NF-S-3-short | 0.837 s | 2 | 1.686 s |
| NF-S-25-short | 0.173 s | 0 | 0.000 s |
| NF-S-3-medium | 0.312 s | 1 | 0.846 s |
| NF-S-25-medium | 0.168 s | 0 | 0.000 s |
| NF-S-3-long | 4.613 s | 3 | 1.380 s |
| NF-S-25-long | 0.170 s | 0 | 0.000 s |

All six trace byte totals match saved PCM frames. Actual chunks were placed at sample-accurate arrival positions; zero insertion renders network gaps. Future-aware delayed versions are diagnostic, not a deployable buffer guarantee. Fresh results are not pooled with the earlier 14-stream benchmark.

## Expression, emotional delivery and prosody

The API documents expression cues such as excitement/whispering/shouting, nonverbal sounds and pacing; there is no tested generic emotion parameter. All 13 documented v3.0 tags were exercised in English and four in Hindi. Models/condition order were hidden for paired judgments; the requested cue is necessarily disclosed in the paired stage. An earlier blind stage receives audio alone, without intended text, model or cue.

| Model | Language | Tag | Initial trial result | Provisional pair result |
|---|---|---|---|---|
| timbre-v3.0 | en-IN | `<laugh>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<giggle>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<sigh>` | header-only / no audio | not assessable |
| timbre-v3.0 | en-IN | `<exhales>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<sniffles>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<yawns>` | header-only / no audio | not assessable |
| timbre-v3.0 | en-IN | `<coughs>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<clears throat>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<whispers>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<shouting>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<excited>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<slow>` | valid audio | cue_demonstrated |
| timbre-v3.0 | en-IN | `<pauses>` | valid audio | not_distinguished |
| timbre-v2.5 | en-IN | `<excited>` | valid audio | no_literal_tag_detected |
| timbre-v2.5 | en-IN | `<whispers>` | valid audio | no_literal_tag_detected |
| timbre-v2.5 | en-IN | `<pauses>` | valid audio | no_literal_tag_detected |
| timbre-v3.0 | hi-IN | `<excited>` | valid audio | cue_demonstrated |
| timbre-v3.0 | hi-IN | `<whispers>` | valid audio | cue_demonstrated |
| timbre-v3.0 | hi-IN | `<slow>` | valid audio | cue_demonstrated |
| timbre-v3.0 | hi-IN | `<pauses>` | valid audio | cue_demonstrated |
| timbre-v2.5 | hi-IN | `<excited>` | valid audio | no_literal_tag_detected |
| timbre-v2.5 | hi-IN | `<pauses>` | valid audio | no_literal_tag_detected |

`cue_demonstrated` requires the pair judge to prefer the tagged clip for the intended cue, identify that cue and retain spoken content without a literal tag flag. `not_distinguished` and `uncertain_or_control_preferred` are unresolved, not definitive proof that a tag is unsupported. No-audio trials fail delivery outright. v2.5 and unknown-tag controls check audible words/content; no literal tag detected does not independently prove the internal stripping implementation.

In 5/9 documented stripping controls (v2.5/unknown tags), the model nevertheless preferred the tagged-condition delivery for the requested cue. Stochastic rendering and judge bias are not separated here; cue judgments are screening observations, not validated tag pass rates.

## Naturalness and prosody screen

Configured/returned audio judge: gemini-3.8-flash. 66 blind clip assessments and 29 paired comparisons. Rubric: 1 severe problems, 3 noticeable issues but understandable, 5 natural/appropriate/clear. Scores are one model’s provisional ratings, not human MOS or native-speaker approval. Existing human ratings and critical-term correctness remain unchanged.

| Repeated untagged English prompts | Rated clips | Naturalness mean /5 | Prosody mean /5 | Intelligibility mean /5 |
|---|---:|---:|---:|---:|
| timbre-v3.0 | 9 | 3.22 | 3.11 | 4.00 |
| timbre-v2.5 | 9 | 3.22 | 3.11 | 4.00 |

Three repeated texts and different voices prevent a general model-quality ranking. Per-clip reasons, observed delivery and blind transcripts are in `blind_ratings.csv`; per-tag comparisons are in `pair_ratings.csv` and `tag_evidence.csv`.

A calibration clip deliberately adds an 80 ms tone and 900 ms silence before intact speech. The judge missed that planted gap, despite correctly transcribing the speech. It also did not flag the reconstructed stream gaps. Its silence/timing judgments therefore cannot validate playback or certify continuous audio. The negative control is unchanged speech. This two-control check does not calibrate all naturalness/emotion ratings; those remain screening observations.

## Speed controls

| Model | Requested speed | Audio duration | Ratio to speed 1.0 |
|---|---:|---:|---:|
| timbre-v3.0 | 0.85 | 3.440 s | 1.075 |
| timbre-v3.0 | 1.15 | 2.960 s | 0.925 |
| timbre-v2.5 | 0.85 | 3.200 s | 1.250 |
| timbre-v2.5 | 1.15 | 2.365 s | 0.924 |

Single-trial durations move in the expected direction for both speeds/models; stochastic synthesis means exact reciprocal scaling is not established.

## Empty audio and numeric readings

| Case | HTTP | Failure |
|---|---:|---|
| NF-T-3-en-sigh | 200 | 44-byte header, zero decoded PCM frames |
| NF-T-3-en-yawns | 200 | 44-byte header, zero decoded PCM frames |
| NF-C-3-raw | 200 | 44-byte header, zero decoded PCM frames |
| NF-N-3-hi | 200 | 44-byte header, zero decoded PCM frames |
| NF-T-3-en-sigh-recheck-48000 | 200 | 44-byte header, zero decoded PCM frames |
| NF-C-3-raw-recheck-24000 | 200 | 44-byte header, zero decoded PCM frames |

The eight rechecks yielded six valid clips and two further empty outputs. Some 24 kHz trials recover; one 48 kHz sigh trial still fails. A sample-rate change is not a consistent fix. Raw numeric text initially failed on v3.0; its 24 kHz recheck failed and 48 kHz recheck produced audio. Keep original attempts in the denominator.

| Numeric case with audio | Blindly heard by the audio model |
|---|---|
| NF-C-3-spoken | The change was minus 2.5%. The pin is 0070. The call starts at 9:05 AM. |
| NF-C-25-raw | The change was negative 2.5%. The pin is 0070. The call starts at 9:05 a.m. |
| NF-C-25-spoken | The change was minus 2.5%. The PIN is 0070. The call starts at 9:05 AM. |
| NF-C-3-raw-recheck-48000 | The change was -2.5%. The pin is 0070. The call starts at 9:5 AM. |

Blind transcripts are provisional listening evidence. Do not infer correctness just from fluent audio. Continue explicitly verbalizing minus signs, leading-zero PIN digits and unambiguous times, followed by critical-slot verification.

## Recommended changes and next validation

1. Decode and count PCM frames before declaring TTS success; reject header-only responses. Use bounded retries or a reviewed fallback while retaining first-attempt failures.
2. For non-interactive files, REST avoids output-stream starvation but retains the full generation wait. For interactive pilots, consider the tested v2.5 configuration with queueing and connection reuse; validate larger paired traffic before selecting a model.
3. Use only documented v3.0 tags. Test intended cues with the chosen voice/language; avoid assuming all tags deliver correctly merely because the request returns 200.
4. Keep speed changes conservative; verify content and naturalness alongside pacing. Preserve explicit language and model-specific voices.
5. Native listeners should review ambiguous tag effects, naturalness and critical numeric readings. Test an actual online jitter buffer and interruption behavior separately; the present reconstruction is not a handset/Exotel test.

## Reproduce and inspect

Credit-free replay: `python run_evaluation.py --mode replay --part all --reports`. Standalone follow-up: `python scripts/analyze_timbre_followup.py`. Open `results/timbre_followup/index.html` for all successful clips and both playback reconstructions. Raw header-only WAVs and all request records are preserved in the same evidence folder.

Optional new paid collection requires `python scripts/timbre_followup.py --live --judge-live`; cached successful requests/judgments are reused, and existing failed trials are retained rather than silently retried. The listed rechecks have their own IDs. `python scripts/judge_playback_checks.py --live` produces the separate playback/control screen. No API access is used by replay.
