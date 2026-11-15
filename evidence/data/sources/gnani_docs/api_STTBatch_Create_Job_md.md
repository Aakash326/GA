> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Create job

> Create a new batch transcription job with uploaded files, a ZIP, or public URLs.

## Overview

Part of [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md), which covers the whole flow, models, languages and limits.

Create a new batch transcription job. The job is created in `CREATED` status with your audio accepted — it does **not** start transcription yet. The response is the same for `prisma-v3.0` and Prisma v2.5.

Call [Start job](https://docs.gnani.ai/api/STTBatch/Start_Job.md) next.

| Method | Best for | Endpoint | Content-Type |
| - | - | - | - |
| Direct upload / ZIP | Files on your machine or CI (up to 10 MB per file) | `POST /stt/v3/batch/jobs` | `multipart/form-data` |
| Public URL / cloud storage | HTTPS links, including S3 presigned URLs, or a cloud-storage path | `POST /stt/v3/batch/jobs` | `application/json` |
| [Presigned upload](#presigned-upload-large-files) | Large files (up to 5 GiB per file) | `POST /stt/v3/batch/v2/jobs` | `application/json` |

The `config` object is the same for all three, including for `prisma-v3.0`.

Authenticated private bucket access is **not** supported.

The **Try it** playground uses the **public URL** (`application/json`) body below. For file upload, use the multipart cURL examples. The presigned upload endpoint has no playground.

## Authentication

| Header | Required | Description |
| - | - | - |
| `X-API-Key-ID` | Yes | Your Gnani API key |

## Request body

### Public URL (`application/json`) — Try it

| Field | Type | Required | Description |
| - | - | - | - |
| `config.model` | string | Yes | `"prisma-v2.5"` (Prisma v2.5) or `"prisma-v3.0"` (Prisma v3.0). See [Models](https://docs.gnani.ai/api/STT/models/overview.md). |
| `config.language_code` | string | Yes | Prisma v3.0: `indic-auto`, or 1–4 comma-separated codes (`"hi-IN,en-IN"`); the language is identified per segment. Prisma v2.5: one code, e.g. `en-IN`, or up to **3** comma-separated codes to have the language identified per file. See [Language identification](https://docs.gnani.ai/api/STTBatch/Introduction.md#language-identification) |
| `config.format` | string | No | **Prisma v3.0 only.** `verbatim`, `transcribe` or `codemix`. See [Output style](https://docs.gnani.ai/api/STTBatch/Introduction.md#output-style) |
| `config.keyterms` | string\[] | No | **Prisma v3.0 only.** Words or short phrases to favour, up to 200. See [Context](https://docs.gnani.ai/api/STTBatch/Introduction.md#context) |
| `config.topic` | string | No | **Prisma v3.0 only.** What the recordings are about, 30–1,600 characters. See [Context](https://docs.gnani.ai/api/STTBatch/Introduction.md#context) |
| `config.speaker_names` | string\[] | No | **Prisma v3.0 only.** Names that may be spoken, 1–4. See [Context](https://docs.gnani.ai/api/STTBatch/Introduction.md#context) |
| `config.mode` | string | No | `"transcribe"`. Unrelated to `format`. |
| `config.with_diarization` | boolean | No | Default `false`. With `prisma-v3.0`, speaker labels are produced either way; this flag only decides whether a diarization failure fails the file. |
| `config.num_speakers` | integer | No | Most speakers to separate, `1`–`8` (default `5`). Speakers are counted automatically; this is an upper limit |
| `config.is_multi_channel` | boolean | No | Default `false` |
| `config.with_denoise` | boolean | No | Default `false`. Enhance (denoise) the audio before transcription — see [Speech enhancement](https://docs.gnani.ai/api/STTBatch/Introduction.md#speech-enhancement-denoising) |
| `config.bias_list` | string\[] | No | Words to boost in recognition (max 100, single words, letters only) — see [Word boosting](https://docs.gnani.ai/api/STTBatch/Introduction.md#word-boosting). With `prisma-v3.0` it is the older name of `config.keyterms`. |
| `config.bias_score` | number | No | Boost strength: `0.0`, `0.5`, `1.0`, `1.5` or `2.0`; `1.0` if `bias_list` is sent without it. Ignored with `prisma-v3.0`. What each value does is in the [Word boosting](https://docs.gnani.ai/api/STTBatch/Introduction.md#word-boosting) table. |
| `source.type` | string | Yes | `"cloud_storage"` |
| `source.provider` | string | No | Cloud storage provider, for example `"aws_s3"` |
| `source.auth.mode` | string | Yes | `"public"` |
| `source.paths` | string\[] | Yes | Public HTTPS URLs (presigned URLs work), or a cloud-storage path such as `s3://my-bucket/calls/`. A path ending in `/` expands to every audio file under that prefix. **No 10 MB cap here** — cloud files are bounded by the 4-hour duration limit, not by size. See [Limits](https://docs.gnani.ai/api/STTBatch/Introduction.md#limits) |
| `callback_url` | string | No | Webhook URL — leave empty in Try it if unused |

URLs are validated at **Start Job**, not at create.

### Multipart upload (`multipart/form-data`)

Use cURL / your client — not the Try it panel.

| Field | Type | Required | Description |
| - | - | - | - |
| `config` | string (JSON) | Yes | STT config. Required: `model`, `language_code` (one code, or several comma-separated — see [Language identification](https://docs.gnani.ai/api/STTBatch/Introduction.md#language-identification)). Optional: `mode` (default `transcribe`), `with_diarization`, `num_speakers` (most speakers to separate, `1`–`8`, default `5`), `is_multi_channel`, `with_denoise` (default `false` — see [Speech enhancement](https://docs.gnani.ai/api/STTBatch/Introduction.md#speech-enhancement-denoising)), `bias_list` and `bias_score` (see [Word boosting](https://docs.gnani.ai/api/STTBatch/Introduction.md#word-boosting)). Prisma v3.0 only: `format`, `keyterms`, `topic` and `speaker_names` (see [Prisma v3.0 options](https://docs.gnani.ai/api/STTBatch/Introduction.md#prisma-v3-0-options)) |
| `files` | file | Yes | Audio or ZIP. Max **100** files/job, **10 MB** per file, ZIP up to **50 MB** compressed / **200 MB** decompressed. These caps apply to uploads only — see [Limits](https://docs.gnani.ai/api/STTBatch/Introduction.md#limits) |
| `callback_url` | string | No | HTTPS webhook. See [Webhook sample payloads](https://docs.gnani.ai/api/STTBatch/Introduction.md#webhooks) |

Send `config` as a form field with `Content-Type: application/json` (see cURL `-F '...;type=application/json'`).

## Example cURL

### Direct upload (live-verified)

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  -F 'config={"model":"prisma-v2.5","language_code":"en-IN","mode":"transcribe","with_diarization":false,"is_multi_channel":false};type=application/json' \
  -F "files=@./customer_call.wav"
```

### Prisma v3.0

Set `model` to `prisma-v3.0` in `config` to use [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md). It works with every way of creating a job. The model identifies the language itself, and `config` accepts `format`, `keyterms`, `topic` and `speaker_names`. See [Prisma v3.0 options](https://docs.gnani.ai/api/STTBatch/Introduction.md#prisma-v3-0-options).

The smallest `prisma-v3.0` config is:

```json theme={null}
{"model": "prisma-v3.0", "language_code": "auto"}
```

#### Inline upload (multipart)

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  -F 'config={"model":"prisma-v3.0","language_code":"auto","format":"codemix","speaker_names":["Rahul","Anita"]};type=application/json' \
  -F "files=@./call-1.wav" \
  -F "files=@./call-2.mp3"
```

#### Cloud storage (JSON)

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  --data '{
    "config": {
      "model": "prisma-v3.0",
      "language_code": "hi-IN,en-IN",
      "format": "transcribe",
      "topic": "Loan collection calls for a retail credit card portfolio",
      "keyterms": ["HDFC Bank", "EMI", "खाता नंबर"],
      "with_diarization": true,
      "num_speakers": 2
    },
    "source": {
      "type": "cloud_storage",
      "provider": "aws_s3",
      "auth": { "mode": "public" },
      "paths": ["s3://my-bucket/calls/"]
    },
    "callback_url": "https://example.com/hooks/batch"
  }'
```

The presigned upload example is [below](#presigned-upload-large-files).

### Public URL

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  --data '{
    "config": {
      "model": "prisma-v2.5",
      "language_code": "en-IN",
      "mode": "transcribe"
    },
    "source": {
      "type": "cloud_storage",
      "auth": { "mode": "public" },
      "paths": ["https://cdn.example.com/audio/call-001.mp3"]
    }
  }'
```

### Diarization (2 speakers)

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  -F 'config={"model":"prisma-v2.5","language_code":"en-IN","mode":"transcribe","with_diarization":true,"num_speakers":2};type=application/json' \
  -F "files=@./stereo_call.wav"
```

### Speech enhancement (noisy audio)

Set `with_denoise: true` to clean the recording before it is transcribed. Use it for
noisy call-centre or field recordings; leave it off for clean studio audio, where it
adds processing time without changing the transcript. See
[Speech enhancement](https://docs.gnani.ai/api/STTBatch/Introduction.md#speech-enhancement-denoising).

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  -F 'config={"model":"prisma-v2.5","language_code":"en-IN","mode":"transcribe","with_denoise":true};type=application/json' \
  -F "files=@./noisy_call.wav"
```

It works the same way on the public-URL body:

```json theme={null}
{
  "config": {
    "model": "prisma-v2.5",
    "language_code": "en-IN",
    "mode": "transcribe",
    "with_denoise": true
  },
  "source": {
    "type": "cloud_storage",
    "auth": { "mode": "public" },
    "paths": ["https://cdn.example.com/audio/noisy-call-001.mp3"]
  }
}
```

## Presigned upload (large files)

Use a presigned upload for files too large for a direct upload, up to **5 GiB** per file. It works with every model, including `prisma-v3.0`. You create the job, upload each file to a presigned URL, then start the job.

| Step | Request |
| - | - |
| 1. Create the job | `POST /stt/v3/batch/v2/jobs` with a JSON body `{config, source, callback_url}`. `source.type` is `"direct_upload_url"` and `source.files` lists the files to upload. |
| 2. Upload each file | `PUT` the file to its URL from the `uploads` array in the response. |
| 3. Start the job | `POST /stt/v3/batch/jobs/{job_id}/start`. See [Start job](https://docs.gnani.ai/api/STTBatch/Start_Job.md). |

```bash theme={null}
# 1. Create
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/v2/jobs \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  --data '{
    "config": { "model": "prisma-v3.0", "language_code": "ta-IN", "keyterms": ["Chennai", "UPI"] },
    "source": { "type": "direct_upload_url", "files": [{ "filename": "town-hall.m4a" }] }
  }'

# 2. Upload the file to uploads[0].url from the response
curl -T town-hall.m4a '<uploads[0].url>'

# 3. Start
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs/<job_id>/start \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

The response is the same `201` as for any other job (see [Response](#response)) with an extra `uploads` array that holds the upload URLs.

## Example — Python SDK

The [Python SDK](https://docs.gnani.ai/python-sdk/speech-to-text-batch.md) builds the multipart request for you, checks file limits before uploading, and sends only the file name (never a path).

```python Create only theme={null}
from gnani.stt import GnaniSTTBatchClient

client = GnaniSTTBatchClient()   # reads GNANI_API_KEY

job = client.create_job(
    "customer_call.wav",         # path, directory, glob, ZIP, bytes, or public URLs
    language_code="hi-IN",
    start=False,                 # create only; call job.start() when ready
)
print(job.id, job.status)        # CREATED
```

```python Diarization (2 speakers) theme={null}
job = client.create_job(
    "customer_call.wav",
    language_code="en-IN",
    speakers=2,                  # sets with_diarization and num_speakers
    start=False,
)
```

```python Noisy audio + word boosting theme={null}
job = client.create_job(
    "customer_call.wav",
    language_code="hi-IN",
    denoise=True,                          # with_denoise
    bias_words=["HDFC", "Prisma", "EMI"],  # bias_list
    bias_score=1.5,
    start=False,
)
```

```python Public URLs theme={null}
job = client.create_job(
    ["https://cdn.example.com/a.mp3", "https://cdn.example.com/b.mp3"],
    language_code="en-IN",
    start=False,
)
```

`create_job()` starts the job right away unless you pass `start=False`. For the whole flow in one call, use `client.transcribe(...)`.

| SDK parameter | API `config` field |
| - | - |
| `language_code` | `language_code` |
| `diarization` / `speakers` | `with_diarization` / `num_speakers` |
| `multi_channel` | `is_multi_channel` |
| `denoise` | `with_denoise` |
| `bias_words` / `bias_score` | `bias_list` / `bias_score` |
| `callback_url` | `callback_url` |

## Response

### Success — multipart upload (`201`)

```json theme={null}
{
  "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
  "status": "CREATED",
  "total_files_accepted": 1,
  "created_at": "2026-07-28T07:26:50.926489Z",
  "message": "1 file(s) uploaded. Call POST /v1/jobs/{job_id}/start to begin processing."
}
```

Save `job_id`. Always start with:

```text theme={null}
POST /stt/v3/batch/jobs/{job_id}/start
```

(even if the message mentions `/v1/jobs/...`)

### Success — public URL create (`201`)

```json theme={null}
{
  "job_id": "019fa79c-ec88-770c-b498-371fc21fb40e",
  "status": "CREATED",
  "created_at": "2026-07-28T07:25:07.137907Z",
  "message": "Job created. Call POST /stt/v3/batch/jobs/{job_id}/start to begin processing.",
  "total_files_accepted": null
}
```

### Error responses

**401 Missing API key**

```json theme={null}
{
  "detail": {
    "error_code": "MISSING_API_KEY",
    "message": "Missing API key",
    "status_code": 401
  }
}
```

**400 Unsupported language**

```json theme={null}
{
  "error": "UNSUPPORTED_LANGUAGE",
  "message": "Value error, This service does not support language_code 'xx-XX'. Supported languages: bn-IN, en-IN, gu-IN, hi-IN, kn-IN, ml-IN, mr-IN, pa-IN, ta-IN, te-IN"
}
```

**400 Invalid config (Prisma v3.0 options)**

```json theme={null}
{
  "error": "INVALID_CONFIG",
  "message": "Invalid config: … Value error, send one of: keyterms, topic, topic + keyterms, or speaker_names (got keyterms, speaker_names) …"
}
```

The text after `Value error,` says what is wrong:

| Cause | Reason |
| - | - |
| `format`, `keyterms`, `topic` or `speaker_names` sent with another model | `format, keyterms are only supported with model 'prisma-v3.0'` (lists the fields you sent) |
| 5 or more codes in `language_code` | `prisma-v3.0 accepts at most 4 candidate languages (got 5); use "auto" to let the model identify the language among all supported languages` |
| Unsupported combination of context fields | `send one of: keyterms, topic, topic + keyterms, or speaker_names (got keyterms, speaker_names)` |
| `format` is not one of the three styles | `input should be 'verbatim', 'transcribe' or 'codemix'` |
| Too many keyterms | `keyterms accepts at most 200 items (got 201)` |
| `topic` length | `topic must be 30-1600 characters (got 12)` |
| Too many names | `speaker_names accepts at most 4 names (got 5)` |
| A name that spans several lines | `speaker_names must each be a single line` |
| `<\|` or `\|>` in `keyterms`, `topic` or `speaker_names` | `keyterms must not contain the tag marker '<\|' or '\|>'` |

An unsupported language code, or `auto` mixed with other codes, is rejected the same way on every model.

Other `400` errors on this endpoint:

| `error` | When | Example `message` |
| - | - | - |
| `UNSUPPORTED_LANGUAGE` | `language_code` is missing | `Field required` |
| `INVALID_CONFIG` | The `config` part is missing | `Invalid config: …` (the message names the missing part) |
| `INVALID_CONFIG` | A file has an extension Batch does not accept | `File 'a.xyz' has unsupported format. Supported: ['.aac', '.amr', '.flac', '.m4a', '.mp3', '.mp4', '.ogg', '.opus', '.wav', '.webm']` |
| `NO_FILES_PROVIDED` | The upload has no files | `At least one file must be provided` |
| `FILE_TOO_LARGE` | A file is over 10 MB (use a presigned upload for larger files) | `File 'a.wav' is 11.2 MB — exceeds the 10 MB limit.` |

A `config` part that is not valid JSON currently returns `500 Internal Server Error`. Send valid JSON.

**job\_id** `string`

Unique job identifier. Required for Start / Status / Files / Cancel.

**status** `string`

Always `CREATED` on success.

**total\_files\_accepted** `integer`

Number of files accepted for multipart/ZIP uploads. May be `null` for public-URL creates.

## Webhook samples

If you pass `callback_url`, Gnani sends a `POST` to your URL when the job finishes.

Full payload examples (including `transcripts[]` / `full_transcript`):

→ **[Webhook samples on Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md#webhooks)**

Events: `job.completed` · `job.partial_failure` · `job.failed` · `job.cancelled`

## Use cases

* Uploading one or many call recordings for offline transcription
* Sending a ZIP of customer audio for batch processing
* Pointing to public HTTPS / S3 presigned URLs without re-uploading files
* Uploading recordings too large for a direct upload (up to 5 GiB per file)

Next: [Start job](https://docs.gnani.ai/api/STTBatch/Start_Job.md)


## OpenAPI

````yaml STTBatch.yml POST /stt/v3/batch/jobs
openapi: 3.1.0
info:
  title: Gnani Speech-to-Text Batch API
  version: 3.0.0
  description: >
    Batch STT Jobs API for asynchronous transcription of long or multiple audio
    files.


    Authenticate every request with the `X-API-Key-ID` header.
servers:
  - url: https://api.vachana.ai
    description: Production
security:
  - ApiKeyAuth: []
paths:
  /stt/v3/batch/jobs:
    post:
      tags:
        - Speech-to-Text (Batch)
      summary: Create Job
      description: >
        Create a batch transcription job from public HTTPS URLs (JSON body).

        For multipart file upload, use cURL with `multipart/form-data` (see docs
        page examples).

        Job is created in `CREATED` status — call Start Job next.
      operationId: create_batch_job
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateJobPublicUrlRequest'
            example:
              config:
                model: prisma-v2.5
                language_code: en-IN
                mode: transcribe
                with_diarization: false
                is_multi_channel: false
                with_denoise: false
              source:
                type: cloud_storage
                auth:
                  mode: public
                paths:
                  - https://cdn.example.com/audio/call-001.mp3
      responses:
        '201':
          description: Job created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CreateJobResponse'
              example:
                job_id: 019fa854-1db0-7e45-a026-7a6b09ff6d7c
                status: CREATED
                created_at: '2026-07-28T10:45:12.769450Z'
                message: >-
                  Job created. Call POST /stt/v3/batch/jobs/{job_id}/start to
                  begin processing.
                total_files_accepted: null
        '401':
          description: Unauthorized
components:
  schemas:
    CreateJobPublicUrlRequest:
      type: object
      required:
        - config
        - source
      properties:
        config:
          $ref: '#/components/schemas/STTConfig'
        source:
          type: object
          required:
            - type
            - auth
            - paths
          properties:
            type:
              type: string
              example: cloud_storage
            provider:
              type: string
              description: Cloud storage provider, for example `aws_s3`.
              example: aws_s3
            auth:
              type: object
              required:
                - mode
              properties:
                mode:
                  type: string
                  example: public
            paths:
              type: array
              items:
                type: string
                format: uri
              example:
                - https://cdn.example.com/audio/call-001.mp3
        callback_url:
          type: string
          format: uri
          description: Optional HTTPS webhook URL for terminal job results
    CreateJobResponse:
      type: object
      properties:
        job_id:
          type: string
          format: uuid
        status:
          type: string
          example: CREATED
        created_at:
          type: string
          format: date-time
        message:
          type: string
        total_files_accepted:
          type: integer
          nullable: true
    STTConfig:
      type: object
      required:
        - model
        - language_code
      properties:
        model:
          type: string
          description: >-
            Model to use. `prisma-v2.5` selects Prisma v2.5; `prisma-v3.0`
            selects Prisma v3.0 (not case-sensitive).
          enum:
            - prisma-v2.5
            - prisma-v3.0
          example: prisma-v2.5
        language_code:
          type: string
          description: >-
            A single BCP-47 code, or any number of comma-separated codes. With
            more than one, the spoken language is identified per file and
            bounded to exactly that set; the first code is the fallback when
            identification is not confident. Supported: bn-IN, en-IN, gu-IN,
            hi-IN, kn-IN, ml-IN, mr-IN, pa-IN, ta-IN, te-IN.

            With `prisma-v3.0`: `indic-auto` (identified per segment among all
            supported languages; `auto` also works), or 1-4 comma-separated
            codes (identified per segment, listening for the listed languages
            first). Order has no meaning, and more than 4 codes returns 400
            INVALID_CONFIG.
          example: en-IN
        mode:
          type: string
          example: transcribe
          default: transcribe
        with_diarization:
          type: boolean
          description: >-
            Label who spoke each segment. With `prisma-v3.0`, speaker labels are
            produced either way; this flag only decides whether a diarization
            failure fails the file.
          example: false
          default: false
        num_speakers:
          type: integer
          minimum: 1
          maximum: 8
          description: >-
            Most speakers to separate (1-8, default 5). Speakers are counted
            automatically; this is an upper limit, not a target.
        is_multi_channel:
          type: boolean
          example: false
          default: false
        with_denoise:
          type: boolean
          description: >-
            Run speech enhancement (denoising) on each file before segmentation
            and transcription. Off by default. Helps noisy recordings such as
            call-centre audio; clean audio is passed through essentially
            unchanged, so enabling it there only adds processing time.
          example: false
          default: false
        bias_list:
          type: array
          maxItems: 100
          items:
            type: string
          description: >-
            Optional. Words to bias recognition towards (brand names, product
            names, Roman-script tokens). Up to 100 single words, letters only
            (Latin or Indic script) - no spaces, digits or punctuation. A
            comma-separated string is also accepted. The same list is applied to
            every segment of every file in the job. Takes effect only for
            languages served by the v2 model; ignored for others. Invalid input
            is rejected when the job is created (400 INVALID_CONFIG). With
            `prisma-v3.0`, this is the older name of `keyterms`: it is used as
            `keyterms` when `keyterms` is not sent, and dropped when both are
            sent.
          example:
            - HDFC
            - Prisma
            - EMI
        bias_score:
          type: number
          enum:
            - 0
            - 0.5
            - 1
            - 1.5
            - 2
          description: >-
            Optional. Boost strength for bias_list. 0.0 turns boosting off. If
            bias_list is sent without bias_score, 1.0 is used. Ignored when
            bias_list is empty. Ignored, and not stored, with `prisma-v3.0`.
          example: 1
        format:
          type: string
          enum:
            - verbatim
            - transcribe
            - codemix
          description: >-
            Output style. Prisma v3.0 only; sending it with another model
            returns 400 INVALID_CONFIG. `verbatim` writes English words in the
            native script and numbers as words; `transcribe` keeps English words
            in Latin and writes digits and symbols; `codemix` keeps English
            words in Latin and mostly speaks numbers out as words. When omitted,
            the model picks per segment: `transcribe` when the only language is
            hi-IN / en-IN (or a list of languages that are all hi-IN / en-IN),
            `verbatim` otherwise.
          example: transcribe
        keyterms:
          type: array
          maxItems: 200
          items:
            type: string
          description: >-
            Words or short phrases to favour, in any script. Prisma v3.0 only.
            Sent with every segment of every file. Allowed on its own, or with
            `topic`; not with `speaker_names`. May also be sent as a
            comma-separated string or a string holding a JSON array.
          example:
            - HDFC Bank
            - EMI
        topic:
          type: string
          minLength: 30
          maxLength: 1600
          description: >-
            What the recordings are about. Prisma v3.0 only. Allowed on its own,
            or with `keyterms`; not with `speaker_names`.
        speaker_names:
          type: array
          minItems: 1
          maxItems: 4
          items:
            type: string
          description: >-
            Names that may be spoken, each on a single line. Prisma v3.0 only.
            Allowed on its own only.
          example:
            - Rahul
            - Anita
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key-ID
      description: Your Gnani API key

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.