> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Create Job

> Create a new batch transcription job with uploaded files, a ZIP, or public URLs.

## Overview

Create a new batch transcription job within your organization. The job is created in `CREATED` status with your audio accepted — it does **not** start transcription yet.

You can then start processing via the **Start Job** endpoint.

| Method | Best for | Content-Type |
| - | - | - |
| Direct upload / ZIP | Files on your machine or CI | `multipart/form-data` |
| Public URL | HTTPS links, including S3 presigned URLs | `application/json` |

Authenticated private bucket access is **not** supported.

## Authentication

| Header | Required | Description |
| - | - | - |
| `X-API-Key-ID` | Yes | Your Gnani Prisma v2.5 API key |

## Request Body

### Multipart upload

**config** `string` *required*

JSON string with STT configuration. Required fields: `model`, `language_code`. Optional: `mode`, `with_diarization`, `num_speakers`, `is_multi_channel`, `bias_list`, `bias_score` (see [Word boosting](#word-boosting-bias_list)).

**files** `file` *required*

Audio file or ZIP archive. Repeat this field for multiple files. Max **100** files per job, **10 MB** per file. ZIP up to **50 MB** compressed.

**callback\_url** `string`

Optional HTTPS webhook URL. When set, Gnani POSTs terminal job results (including `full_transcript`) to this URL.

### Public URL (JSON)

| Field | Type | Required | Description |
| - | - | - | - |
| `config` | object | Yes | STT config object. Optional `bias_list` and `bias_score` — see [Word boosting](#word-boosting-bias_list) |
| `source.type` | string | Yes | `"cloud_storage"` |
| `source.auth.mode` | string | Yes | `"public"` |
| `source.paths` | string\[] | Yes | Public HTTPS URLs |
| `callback_url` | string | No | Webhook URL |

## Word boosting (`bias_list`)

Optionally bias recognition towards words the model tends to get wrong — brand names, product names, Roman-script tokens. Both fields are optional and go **inside `config`**, for the multipart `config` string and the JSON body alike.

| Field | Type | Required | Description |
| - | - | - | - |
| `config.bias_list` | string\[] | No | Up to **100** words. One word per entry — letters only (Latin or Indic script), no spaces, digits or punctuation. A comma-separated string (`"HDFC,Prisma"`) is also accepted. Case does not matter. |
| `config.bias_score` | number | No | One of `0.0`, `0.5`, `1.0`, `1.5`, `2.0`. `0.0` turns boosting off. Defaults to `1.0` when `bias_list` is sent without it. Ignored when there is no `bias_list`. |

```json theme={null}
"config": {
  "model": "prisma-v2.5",
  "language_code": "hi-IN",
  "bias_list": ["HDFC", "Prisma", "EMI"],
  "bias_score": 1.5
}
```

* The same list and score apply to every segment of every file in the job.
* Boosting takes effect only for languages served by the v2 model (`hi-IN`, `en-IN`, `ta-IN`, `bn-IN`, `kn-IN`, `te-IN`, `ml-IN`, `mr-IN`). For anything else it is ignored, not rejected.
* An invalid list or score is rejected when the job is **created** (see the `400 INVALID_CONFIG` error below), unlike the synchronous `POST /stt/v3`, which skips boosting silently.
* Boosted words are not echoed in the transcript; `Get Job Status` shows them in `config`.

## Example cURL

```bash theme={null}
curl -X POST "https://api.vachana.ai/stt/v3/batch/jobs" \
  -H "X-API-Key-ID: <YOUR_API_KEY>" \
  -F 'config={"model":"prisma-v2.5","language_code":"en-IN","mode":"transcribe","with_diarization":false,"is_multi_channel":false};type=application/json' \
  -F "files=@./customer_call.wav"
```

### Example cURL with word boosting

```bash theme={null}
curl -X POST "https://api.vachana.ai/stt/v3/batch/jobs" \
  -H "X-API-Key-ID: <YOUR_API_KEY>" \
  -F 'config={"model":"prisma-v2.5","language_code":"hi-IN","mode":"transcribe","bias_list":["HDFC","Prisma","EMI"],"bias_score":1.5};type=application/json' \
  -F "files=@./customer_call.wav"
```

## Response

### Success (201)

```json theme={null}
{
  "job_id": "019fa259-b084-71eb-94d7-ba4cdf2e64c6",
  "status": "CREATED",
  "total_files_accepted": 1,
  "created_at": "2026-07-27T06:53:34.750193Z",
  "message": "1 file(s) uploaded. Call POST /v1/jobs/{job_id}/start to begin processing."
}
```

Save `job_id`. Always start with `/stt/v3/batch/jobs/{job_id}/start` (even if the message mentions `/v1/jobs/...`).

### Error responses

**400 Unsupported language**

```json theme={null}
{
  "error": "UNSUPPORTED_LANGUAGE",
  "message": "Value error, This service does not support language_code 'xx-XX'. Supported languages: bn-IN, en-IN, gu-IN, hi-IN, kn-IN, ml-IN, mr-IN, pa-IN, ta-IN, te-IN"
}
```

**400 Invalid `bias_list` / `bias_score`**

```json theme={null}
{
  "error": "INVALID_CONFIG",
  "message": "Invalid config: 1 validation error for STTConfig\nbias_list\n  Value error, bias_list entries must be single words, not phrases ..."
}
```

Other reasons: `bias_list entries must be letters only (no digits, punctuation, or symbols)`, `bias_list holds N words; the maximum is 100`, `bias_score must be one of [0.0, 0.5, 1.0, 1.5, 2.0]`.

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

## Use Cases

* Uploading one or many call recordings for offline transcription
* Sending a ZIP of customer audio for batch processing
* Pointing to public HTTPS / S3 presigned URLs without re-uploading files

Use the **Try it** playground to run this request with your API key. Then call **Start Job**.


## OpenAPI

````yaml POST /stt/v3/batch/jobs
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