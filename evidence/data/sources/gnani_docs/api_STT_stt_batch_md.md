> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Batch transcription

> Asynchronous transcription of long or multiple audio files via the Batch Jobs API.

Use **STT Batch** to transcribe long recordings or many files asynchronously.

> [!NOTE]
>
> **Model:**  Not sure which to use? See [Models](https://docs.gnani.ai/api/STT/models/overview.md).

On Batch, Prisma v3.0 is the same model as [REST](https://docs.gnani.ai/api/STT/speech-to-text.md) with `model=prisma-v3.0`: one model for all ten languages, which [identifies the spoken language itself](#language-identification). A `prisma-v3.0` job also accepts four extra `config` options: `format`, `keyterms`, `topic` and `speaker_names` (see [Prisma v3.0 options](#prisma-v3-0-options)).

Everything else about a job is the same on both models: the endpoints, `start`, `cancel`, status and file-results calls, speaker diarization, denoising, limits and webhooks.

**Flow:** create a job → start it → poll until it finishes → download transcripts\
(or receive them on a webhook).

| If you need… | Use |
| - | - |
| Long files, many files, or offline pipelines | **STT Batch** (this section) |
| Short clips (under \~30 seconds), immediate answer | [STT REST](https://docs.gnani.ai/api/STT/speech-to-text.md) |
| Language detection, `codemix`, context hints | [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md) (`config.model: prisma-v3.0`) |
| Live microphone / streaming audio | [STT Realtime](https://docs.gnani.ai/api/STT/stt-websocket.md) |

***

## How it works

```text theme={null}
1. CREATE    POST /stt/v3/batch/jobs
             → 201  job_id   status: CREATED

2. START     POST /stt/v3/batch/jobs/{job_id}/start
             → 202             status: STARTING

3. WAIT      GET  /stt/v3/batch/jobs/{job_id}
             poll every 10s until a terminal status
             (live: STARTING → QUEUED → IN_PROGRESS → COMPLETED)

4. FILES     GET  /stt/v3/batch/jobs/{job_id}/files
             → transcript_url for each completed file

5. DOWNLOAD  GET  <transcript_url>
             → JSON with full_transcript + segments
```

**Important:** creating a job does **not** start transcription. You must call `/start`.

***

## Interactive API reference

These are the same six endpoints as on [docs.gnani.ai](https://docs.gnani.ai/api/STTBatch/Introduction.md). Open an endpoint page and use **Try it** to send a live request with your `X-API-Key-ID`.

| Step | Endpoint | Page | Try it |
| - | - | - | - |
| 1 | `POST /stt/v3/batch/jobs` | [Create job](https://docs.gnani.ai/api/STTBatch/Create_Job.md) | [Try it](https://docs.gnani.ai/api/STTBatch/Create_Job.md) |
| 2 | `POST /stt/v3/batch/jobs/{job_id}/start` | [Start job](https://docs.gnani.ai/api/STTBatch/Start_Job.md) | [Try it](https://docs.gnani.ai/api/STTBatch/Start_Job.md) |
| 3 | `GET /stt/v3/batch/jobs/{job_id}` | [Get job status](https://docs.gnani.ai/api/STTBatch/Get_Job.md) | [Try it](https://docs.gnani.ai/api/STTBatch/Get_Job.md) |
| 4 | `GET /stt/v3/batch/jobs/{job_id}/files` | [Get job files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md) | [Try it](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md) |
| — | `GET /stt/v3/batch/jobs` | [List jobs](https://docs.gnani.ai/api/STTBatch/List_Jobs.md) | [Try it](https://docs.gnani.ai/api/STTBatch/List_Jobs.md) |
| — | `POST /stt/v3/batch/jobs/{job_id}/cancel` | [Cancel job](https://docs.gnani.ai/api/STTBatch/Cancel_Job.md) | [Try it](https://docs.gnani.ai/api/STTBatch/Cancel_Job.md) |

For files over 10 MB, create the job with a presigned upload (`POST /stt/v3/batch/v2/jobs`). It is described on [Create job](https://docs.gnani.ai/api/STTBatch/Create_Job.md#presigned-upload-large-files) and has no **Try it** playground.

**Webhook payload examples:** [Webhooks](#webhooks) — samples for `job.completed`, `job.failed`, and `job.cancelled`.

***

## Before you begin

1. An API key from the Gnani APIs dashboard
2. Audio with **real speech** in a [supported format](#supported-audio-formats)
3. A [supported language code](#supported-languages)

**Base URL**

```text theme={null}
https://api.vachana.ai
```

**Auth** — send on every Batch API request:

```http theme={null}
X-API-Key-ID: <YOUR_API_KEY>
```

Tone-only / silent audio is accepted into a job but fails later with `Empty transcript after 3 retries`.

***

## How do I get the transcript text?

| Option | When to use | What you do |
| - | - | - |
| **A. Polling (default)** | No webhook | Poll job status → `GET /files` → `GET` each `transcript_url` → read `full_transcript` |
| **B. Webhook** | You passed `callback_url` | Receive a POST with `transcripts[]` including `full_transcript` |

`GET /jobs/{job_id}` and `GET /jobs/{job_id}/files` do **not** return `full_transcript`.

***

## Quickstart

### 1. Create

The Prisma v2.5 request below was live-verified.

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  -F 'config={"model":"prisma-v2.5","language_code":"en-IN","mode":"transcribe","with_diarization":false,"is_multi_channel":false};type=application/json' \
  -F "files=@./customer_call.wav"
```

To use Prisma v3.0, set `model` to `prisma-v3.0` in `config`. With `prisma-v3.0`, `language_code` can be `indic-auto`, or 1–4 comma-separated codes (see [Language identification](#language-identification)):

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  -F 'config={"model":"prisma-v3.0","language_code":"auto"};type=application/json' \
  -F "files=@./customer_call.wav"
```

[Try it on Create job](https://docs.gnani.ai/api/STTBatch/Create_Job.md)

Example response:

```json theme={null}
{
  "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
  "status": "CREATED",
  "total_files_accepted": 1,
  "created_at": "2026-07-28T07:26:50.926489Z",
  "message": "1 file(s) uploaded. Call POST /v1/jobs/{job_id}/start to begin processing."
}
```

### 2. Start

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs/019fa79e-81f9-7a8a-a446-6eff16ddec30/start \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

[Try it on Start job](https://docs.gnani.ai/api/STTBatch/Start_Job.md)

```json theme={null}
{
  "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
  "status": "STARTING",
  "message": "Job start accepted. File validation and queueing are running in the background. Poll GET /stt/v3/batch/jobs/{job_id} to track progress."
}
```

### 3. Poll until `COMPLETED`

```bash theme={null}
curl --request GET \
  --url https://api.vachana.ai/stt/v3/batch/jobs/019fa79e-81f9-7a8a-a446-6eff16ddec30 \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

[Try it on Get job status](https://docs.gnani.ai/api/STTBatch/Get_Job.md)

### 4. Get `transcript_url`, then download text

```bash theme={null}
curl --request GET \
  --url 'https://api.vachana.ai/stt/v3/batch/jobs/019fa79e-81f9-7a8a-a446-6eff16ddec30/files?status=COMPLETED' \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

[Try it on Get job files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md)

```bash theme={null}
curl -L "<transcript_url>"
```

```json theme={null}
{
  "full_transcript": "hello how can i help you today i am calling about my recent order number 12345",
  "model": "prisma-v2.5",
  "language_code": "en-IN",
  "duration_seconds": 6.01
}
```

A `prisma-v3.0` job returns the same document with `model` set to `prisma-v3.0` and `language_detected` filled on every segment that has text. See [Get job files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md#transcript-document).

### 5. List jobs

```bash theme={null}
curl --request GET \
  --url 'https://api.vachana.ai/stt/v3/batch/jobs?limit=3' \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

[Try it on List jobs](https://docs.gnani.ai/api/STTBatch/List_Jobs.md)

### 6. Cancel a job

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs/019fa79c-7880-7d05-a528-edc7892ad9ea/cancel \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  --header 'Content-Type: application/json' \
  --data '{"reason":"Docs verification cancel test"}'
```

[Try it on Cancel job](https://docs.gnani.ai/api/STTBatch/Cancel_Job.md)

***

## Quickstart — Python SDK

The [Python SDK](https://docs.gnani.ai/python-sdk/speech-to-text-batch.md) wraps the same four steps — create, start, poll, fetch:

```bash theme={null}
pip install -U "gnani-vachana>=0.8.1"
```

```python theme={null}
from gnani.stt import GnaniSTTBatchClient

client = GnaniSTTBatchClient()   # reads GNANI_API_KEY

# 1. Create — POST /stt/v3/batch/jobs
job = client.create_job(
    "customer_call.wav",
    language_code="en-IN",
    start=False,                 # create only; omit to start automatically
)
print(job.id, job.status)        # CREATED

# 2. Start — POST /stt/v3/batch/jobs/{job_id}/start
job.start()
print(job.status)                # STARTING

# 3. Poll until a terminal status — GET /stt/v3/batch/jobs/{job_id}
job.wait()                       # polls every 10 s
print(job.status, job.percent)   # COMPLETED 100

# 4. Fetch transcripts — GET .../files, then each transcript_url
for f in job.files():
    print(f.name, f.status)
    if f.ok:
        print(f.text)            # full_transcript

job.save("./outputs")
```

Keep `job.id` to resume later with `client.get_job(job_id)`. For `asyncio` use `AsyncGnaniSTTBatchClient`. To do all four steps in one call, use `client.transcribe(...)` — see the [SDK guide](https://docs.gnani.ai/python-sdk/speech-to-text-batch.md#quick-start).

***

## Configuration

| Field | Type | Required | Default | Description |
| - | - | - | - | - |
| `model` | string | Yes | — | `"prisma-v2.5"` (Prisma v2.5) or `"prisma-v3.0"` (Prisma v3.0, not case-sensitive) |
| `language_code` | string | Yes | — | One code, or several comma-separated codes. Prisma v3.0 also accepts `"auto"`. See [Language identification](#language-identification) and [Supported languages](#supported-languages) |
| `format` | string | No | see [Output style](#output-style) | **Prisma v3.0 only.** `verbatim`, `transcribe` or `codemix` |
| `keyterms` | string\[] | No | — | **Prisma v3.0 only.** Words or short phrases to favour, up to 200 — see [Context](#context) |
| `topic` | string | No | — | **Prisma v3.0 only.** What the recordings are about, 30–1,600 characters |
| `speaker_names` | string\[] | No | — | **Prisma v3.0 only.** Names that may be spoken, 1–4 |
| `mode` | string | No | `"transcribe"` | Use `"transcribe"` for now. It is unrelated to `format`. |
| `with_diarization` | boolean | No | `false` | Enable speaker diarization. With `prisma-v3.0`, speaker labels are produced either way; this flag only decides whether a diarization failure fails the file. |
| `num_speakers` | integer | No | `5` | Most speakers to separate, `1`–`8`. Speakers are counted automatically; this is an upper limit, not a target |
| `is_multi_channel` | boolean | No | `false` | `true` only for true multi-channel audio |
| `with_denoise` | boolean | No | `false` | Enhance (denoise) the audio before transcription — see [Speech enhancement](#speech-enhancement-denoising) |
| `bias_list` | string\[] | No | — | Words to bias recognition towards — see [Word boosting](#word-boosting). With `prisma-v3.0` it is the older name of `keyterms`. |
| `bias_score` | number | No | `1.0` when `bias_list` is set | Boost strength: `0.0`, `0.5`, `1.0`, `1.5` or `2.0` — see [Word boosting](#word-boosting). Ignored, and not stored, with `prisma-v3.0`. |

Inverse Text Normalization (ITN) is **not** supported for STT Batch.

### Prisma v3.0 options

`format`, `keyterms`, `topic` and `speaker_names` exist only for `prisma-v3.0`. Sending any of them with another model returns `400 INVALID_CONFIG`: they are refused, not ignored. They go inside `config`, for every way of creating a job.

#### Output style

| Style | English words | Numbers and symbols |
| - | - | - |
| `verbatim` | written in the native script | spelled out as words |
| `transcribe` | stay in Latin | digits, symbols, currency signs (`12345`, `%`, `₹`) |
| `codemix` | stay in Latin | mostly spoken out as words in the native language |

When you leave `format` out, the model picks a style for each segment: `transcribe` when the only language is `hi-IN` or `en-IN` (or a list of languages that are all `hi-IN` or `en-IN`), and `verbatim` otherwise, including `indic-auto`. English speech is written in Latin in every style. Inverse text normalization is not supported on Batch, so `format` is what controls how numbers are written. For more on the three styles, see [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md#output-styles).

#### Context

Context is sent with **every segment of every file** in the job.

| Field | Limits |
| - | - |
| `keyterms` | Up to 200 items. Words or short phrases, in any script. Duplicates are dropped. |
| `topic` | 30–1,600 characters. |
| `speaker_names` | 1–4 names, each on a single line. |

None of them may contain `<|` or `|>`. `keyterms` and `speaker_names` can also be sent as a comma-separated string, or as a string that holds a JSON array. Use the JSON array form when an item contains a comma.

Send **one** of the combinations below. Anything else returns `400 INVALID_CONFIG` when the job is created.

| You send | Accepted |
| - | - |
| nothing | yes |
| `keyterms` | yes |
| `topic` | yes |
| `topic` + `keyterms` | yes |
| `speaker_names` | yes |
| any other mix (for example `keyterms` + `speaker_names`, or `topic` + `speaker_names`) | **no** — `400 INVALID_CONFIG` |

`bias_list` with `prisma-v3.0`: if `keyterms` is not sent, `bias_list` is used as `keyterms`, and counts as `keyterms` in the table above. If both are sent, `keyterms` wins and `bias_list` is dropped. `bias_score` is ignored. [Get job status](https://docs.gnani.ai/api/STTBatch/Get_Job.md) shows the result: `keyterms` filled, `bias_list` and `bias_score` `null`.

> [!WARNING]
>
> Context can make a model **less** accurate on some audio. Compare a job with and without it on your own recordings before relying on it.

```json theme={null}
"config": {
  "model": "prisma-v3.0",
  "language_code": "hi-IN,en-IN",
  "format": "transcribe",
  "topic": "Loan collection calls for a retail credit card portfolio",
  "keyterms": ["HDFC Bank", "EMI", "खाता नंबर"]
}
```

For tips on writing keyterms, see [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md#context).

#### Not available on Batch

These REST options are not supported on Batch:

| REST option | Why |
| - | - |
| `previous_text` | It describes the clip just before a single request. A batch file is cut into many segments that are transcribed in parallel. |
| `enable_substitution`, `substitution_map` | Not supported on Batch. |

### Word boosting

> [!NOTE]
>
> This section describes Prisma v2.5. With `prisma-v3.0`, `bias_list` is the older name of `keyterms` and `bias_score` is ignored. See [Prisma v3.0 options](#prisma-v3-0-options).

`bias_list` nudges recognition towards words the model tends to get wrong — brand
names, product names, Roman-script tokens. Both fields are optional and go inside
`config`, for the public-URL body and for the multipart `config` field alike:

```json theme={null}
"config": {
  "model": "prisma-v2.5",
  "language_code": "hi-IN",
  "bias_list": ["HDFC", "Prisma", "EMI"],
  "bias_score": 1.5
}
```

| Field | Rule |
| - | - |
| `bias_list` | JSON array of up to **100** words. One word per entry — letters only (Latin or Indic script), no spaces, digits or punctuation. A comma-separated string (`"HDFC,Prisma"`) is also accepted. Case does not matter. |
| `bias_score` | One of the values in the table below. If you send `bias_list` without it, `1.0` is used. A score without a list does nothing. |

| `bias_score` | Effect |
| - | - |
| `0.0` | Off (same as leaving it out) |
| `0.5` | Light nudge |
| `1.0` | Typical starting point, and the default when `bias_list` is sent |
| `1.5` | Stronger |
| `2.0` | Maximum |

Start at `1.0` and raise it only if a word is still missed. A stronger score can make the model favour a listed word where it was not spoken.

The same list and score are applied to every segment of every file in the job. An
invalid list or score is rejected when the job is **created** (`400 INVALID_CONFIG`) — unlike the
synchronous `POST /stt/v3`, which would silently skip boosting.

Boosting only takes effect for languages served by the v2 model (`hi-IN`, `en-IN`,
`ta-IN`, `bn-IN`, `kn-IN`, `te-IN`, `ml-IN`, `mr-IN`, `gu-IN`, `pa-IN`); it is ignored, not rejected,
for anything else. Boosted words are not echoed in the transcript, only in the job's
`config`.

### Speech enhancement (denoising)

Set `with_denoise: true` to have each file cleaned up before it is segmented and
transcribed:

```json theme={null}
"config": {
  "model": "prisma-v2.5",
  "language_code": "en-IN",
  "with_denoise": true
}
```

It is **off by default**, and worth turning on only when your audio needs it:

| Your audio | Recommendation |
| - | - |
| Noisy calls, background hum, street or field recordings | Enable — this is what it is for |
| Clean studio or headset audio | Leave off — enhancement passes clean speech through nearly unchanged, so you only pay the extra processing time |

Notes:

* The whole pipeline sees the cleaned audio — speech detection, transcription and
  diarization all run on it, so timestamps and speaker labels come from the enhanced
  signal.
* It **adds processing work** per file — on the order of a quarter of the audio's
  duration again — so a job with `with_denoise` takes longer to reach `COMPLETED`.
* It is **not conditional on how noisy the file is** — every file in the job is
  enhanced. Set it per job, on the jobs that need it.
* Nothing else changes: the transcript JSON, webhook payloads and billing are the same
  (billing is per audio duration either way).
* The setting is echoed back as `config.with_denoise` on
  [Get job status](https://docs.gnani.ai/api/STTBatch/Get_Job.md).

> [!NOTE]
>
> Enhancement is applied where the platform has it enabled. If it is switched off for
> maintenance, a job that asked for it still runs to `COMPLETED` — transcribed from the
> original audio rather than failing.

***

## Limits

Limits depend on **how you send the audio**. The 10 MB, ZIP and file-count limits below apply
to **direct upload only** — they do not apply to files fetched from cloud storage.

### Every file, whichever way it arrives

| Limit | Value |
| - | - |
| Max audio duration | **4 hours** per file |
| Min audio duration | **0.1 s** per file |
| Max speech segments detected | **5,000** per file |

A file longer than 4 hours is rejected with `AUDIO_TOO_LONG`. Split it first.

### Direct upload (`multipart/form-data`)

| Limit | Value |
| - | - |
| Max audio files per job | **100** |
| Max size per file | **10 MB** |
| Max ZIP compressed size | **50 MB** |
| Max ZIP decompressed size | **200 MB** |
| Max ZIP compression ratio | **50:1** |

The 100-file limit counts everything in the job, including files expanded out of a ZIP.

### Presigned upload (`source.type: "direct_upload_url"`)

For files too large for direct upload. See [Create job](https://docs.gnani.ai/api/STTBatch/Create_Job.md#presigned-upload-large-files).

| Limit | Value |
| - | - |
| Max size per file | **5 GiB** |

### Cloud storage (`source.type: "cloud_storage"`)

| Limit | Value |
| - | - |
| Max size per file | **No byte limit** — bounded by the 4-hour duration cap above |
| Max download time per file | **30 minutes** |
| Max files per job | **Not currently capped** |

> [!NOTE]
>
> **The 10 MB limit is for uploads only.** Sending a 200 MB recording as a `cloud_storage`
> path is fine — what matters is that it is under 4 hours and downloadable within 30
> minutes. Uploading that same file through `multipart/form-data` would be rejected.

> [!WARNING]
>
> A path ending in `/` is treated as a **folder** and expands to every supported audio
> file under that prefix. Because cloud storage jobs are not file-count capped, a broad
> prefix can enqueue far more audio than you intended — and every file is billed. Point
> at explicit file paths, or a narrow prefix you have checked.

### Results and polling

| Limit | Value |
| - | - |
| `transcript_url` expiry | **1 hour** (`X-Amz-Expires=3600`) |
| Poll interval | **≥ 10 s** (prefer **30 s** for 100+ files) |

The poll interval is guidance, not an enforced limit — but the API is rate limited, so
polling more tightly than this risks `429` responses on your other calls.

***

## Supported languages

| Language | Code | Native Script | Example |
| - | - | - | - |
| Bengali | `bn-IN` | Bengali (বাংলা) | "আমি ভাত খাই" |
| English | `en-IN` | English (Latin) (Accepts English-Hindi mixed audio and generates output in English (Latin script).) | "I am going to the market" |
| Gujarati | `gu-IN` | Gujarati (ગુજરાતી) | "હું બજાર જાઉં છું" |
| Hindi | `hi-IN` | Devanagari (हिन्दी) | "मैं बाज़ार जा रहा हूँ" |
| Kannada | `kn-IN` | Kannada (ಕನ್ನಡ) | "ನಾನು ಮಾರುಕಟ್ಟೆಗೆ ಹೋಗುತ್ತೇನೆ" |
| Malayalam | `ml-IN` | Malayalam (മലയാളം) | "ഞാൻ ചന്തയിലേക്ക് പോകുന്നു" |
| Marathi | `mr-IN` | Devanagari (मराठी) | "मी बाजारात जातोय" |
| Punjabi | `pa-IN` | Gurmukhi (ਪੰਜਾਬੀ) | "ਮੈਂ ਬਾਜ਼ਾਰ ਜਾ ਰਿਹਾ ਹਾਂ" |
| Tamil | `ta-IN` | Tamil (தமிழ்) | "நான் சந்தைக்கு செல்கிறேன்" |
| Telugu | `te-IN` | Telugu (తెలుగు) | "నేను మార్కెట్‌కి వెళ్తున్నాను" |

### Language identification

How the language is chosen depends on the model. If you know the language, pass a single code on either model.

#### Prisma v3.0

`prisma-v3.0` identifies the spoken language itself, so you can send `indic-auto`, or one to four language codes.

| `language_code` | Mode | What happens |
| - | - | - |
| `"indic-auto"` | Auto | The model identifies the language of each segment among all supported languages. |
| `"hi-IN"` or `"hi-IN,en-IN"` (1–4 codes) | Listed languages | The model listens for your languages first, for each segment. If a segment is clearly in another language, it follows that language. |
| 5 or more codes | — | `400 INVALID_CONFIG`. Use `"indic-auto"` instead. |

* **The language is decided per segment**: each stretch of speech between pauses, split again at speaker changes. A call where speakers switch language gets each part in its own language.
* **Your languages are a hint, not a limit.** If a segment is clearly in a language outside your list, it is transcribed and reported in that language.
* **Order does not matter.** Prisma v3.0 has no fallback language.
* At most **4** languages.
* `"auto"` is accepted as another spelling of `"indic-auto"`. Either is stored as `"auto"`.
* The transcript reports the language of each segment in `language_detected`, and the language that covers the most speech in `language_code`. See [Get job files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md#transcript-document).

#### Prisma v2.5

Pass **up to three** codes as a comma-separated list. Each file is then
identified as **one** of exactly those languages and transcribed in it:

```json theme={null}
"language_code": "hi-IN,en-IN"
```

Rules:

* **Maximum three** codes. More returns `400 UNSUPPORTED_LANGUAGE`.
* Every code must be from the table above; one unsupported code rejects the request.
* **Order matters.** The **first** code is the fallback used when identification is not
  confident enough to choose.
* The decision is made **per file**, not per segment — a file is transcribed entirely in
  one language. The resolved language is returned as `language_code` in the transcript
  JSON, so it always tells you what the text is actually in.
* A single code behaves exactly as before, with no identification step.

## Supported audio formats

`.wav` · `.mp3` · `.mp4` · `.flac` · `.ogg` · `.opus` · `.m4a` · `.aac` · `.webm` · `.amr`

***

## Job statuses

| Status | Terminal | Meaning |
| - | - | - |
| `CREATED` | No | Waiting for `/start` |
| `STARTING` | No | Setup running |
| `QUEUED` | No | Files queued |
| `IN_PROGRESS` | No | Transcription running |
| `COMPLETED` | Yes | All succeeded |
| `PARTIAL_FAILURE` | Yes | Mixed results |
| `FAILED` | Yes | Failed |
| `START_FAILED` | Yes | Setup failed — see `cancel_reason` |
| `CANCELLING` | No | Cancel in progress |
| `CANCELLED` | Yes | Cancelled |

***

## Webhooks

Pass `callback_url` at create time to receive a `POST` when the job reaches a terminal state.

| `event` | Triggered when |
| - | - |
| `job.completed` | All files succeeded |
| `job.partial_failure` | Mixed success / failure |
| `job.failed` | All files failed |
| `job.cancelled` | Job cancelled |

The `transcripts` array includes full per-file transcript JSON (with `full_transcript`), so webhook users usually do not need `/files` + `transcript_url`.

Webhooks work the same way for `prisma-v3.0`: same events, same payload. The entries in `transcripts` use the same transcript document as [Get job files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md#transcript-document), where the `prisma-v3.0` differences are described.

Treat webhooks as best-effort. Polling remains the source of truth.

### Sample webhook payload — `job.completed`

```json theme={null}
{
  "event": "job.completed",
  "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
  "org_id": "org_acme123",
  "user_id": "user_abc456",
  "status": "COMPLETED",
  "total_files": 1,
  "completed_files": 1,
  "failed_files": 0,
  "cancelled_files": 0,
  "completed_at": "2026-07-28T07:27:24Z",
  "callback_url": "https://yourapp.com/webhooks/stt",
  "transcripts": [
    {
      "file_id": "6f5e3bcd-add2-479c-8883-a9c27b221f10",
      "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
      "original_path": "customer_call.wav",
      "language_code": "en-IN",
      "duration_seconds": 6.01,
      "model": "prisma-v2.5",
      "mode": "transcribe",
      "segments": [
        {
          "segment_id": 0,
          "start_time": 0.0,
          "end_time": 0.71,
          "text": "hello",
          "speaker_id": 1,
          "confidence": null,
          "language_detected": null,
          "sentiment": null,
          "emotion": null
        },
        {
          "segment_id": 0,
          "start_time": 0.71,
          "end_time": 2.36,
          "text": "how can i help you today",
          "speaker_id": 2,
          "confidence": null,
          "language_detected": null,
          "sentiment": null,
          "emotion": null
        },
        {
          "segment_id": 0,
          "start_time": 2.36,
          "end_time": 6.01,
          "text": "i am calling about my recent order number 12345",
          "speaker_id": 2,
          "confidence": null,
          "language_detected": null,
          "sentiment": null,
          "emotion": null
        }
      ],
      "full_transcript": "hello how can i help you today i am calling about my recent order number 12345",
      "created_at": "2026-07-28T07:27:24Z"
    }
  ]
}
```

### Sample webhook payload — `job.failed`

```json theme={null}
{
  "event": "job.failed",
  "job_id": "019fa79b-a07a-7a3e-93bf-4ee73974dfa2",
  "org_id": "org_acme123",
  "user_id": "user_abc456",
  "status": "FAILED",
  "total_files": 1,
  "completed_files": 0,
  "failed_files": 1,
  "cancelled_files": 0,
  "completed_at": "2026-07-28T07:24:32Z",
  "callback_url": "https://yourapp.com/webhooks/stt",
  "transcripts": []
}
```

### Sample webhook payload — `job.cancelled`

```json theme={null}
{
  "event": "job.cancelled",
  "job_id": "019fa79c-7880-7d05-a528-edc7892ad9ea",
  "org_id": "org_acme123",
  "user_id": "user_abc456",
  "status": "CANCELLED",
  "total_files": 1,
  "completed_files": 0,
  "failed_files": 0,
  "cancelled_files": 1,
  "completed_at": null,
  "callback_url": "https://yourapp.com/webhooks/stt",
  "transcripts": []
}
```

***

## Common mistakes

| Mistake | What happens | Fix |
| - | - | - |
| Forgetting `/start` | Job stays `CREATED` | Call [Start job](https://docs.gnani.ai/api/STTBatch/Start_Job.md) |
| Expecting `full_transcript` on status/`/files` | Field missing | `GET /files` → then `GET transcript_url` |
| Using `/v1/jobs/...` from create message | Wrong path | Use `/stt/v3/batch/jobs/{job_id}/start` |
| Uploading silence / tones | `FAILED` — `Empty transcript after 3 retries` | Use real speech |
| Invalid public URL | `START_FAILED` / file `SKIPPED` | Use reachable HTTPS URLs |
| Polling every 1–2 seconds | Wasted calls | Poll every 10s |
| `with_denoise: true` on clean audio | Job takes longer, transcript barely changes | Enable it only for noisy recordings |
| Expired `transcript_url` | Download fails | Re-call [Get job files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md) |
| `format`, `keyterms`, `topic` or `speaker_names` with `prisma-v2.5` | `400 INVALID_CONFIG` | Set `model` to `prisma-v3.0`, or remove the field |
| `keyterms` with `speaker_names`, or `topic` with `speaker_names` | `400 INVALID_CONFIG` | Send one of the [accepted combinations](#context) |
| 5 or more codes in `language_code` with `prisma-v3.0` | `400 INVALID_CONFIG` | Send up to 4 codes, or `"auto"` |
| `previous_text` or substitution fields | Not supported on Batch | See [Not available on Batch](#not-available-on-batch) |

***

## Support

Docs feedback: [Batch STT docs feedback](https://discord.com/channels/1511338519899930634/1515991436229611571)

**Last verified (Prisma v2.5):** 5 August 2026
Live-checked: Create → Start → Poll → Files → Transcript download, List, Cancel, and error codes `401` / `400` / `404` / `409`.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.