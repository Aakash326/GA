> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Get job files

> List per-file results and transcript URLs for a batch job.

## Overview

Part of [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md), which covers the whole flow, models, languages and limits.

List per-file results for a job. For completed files, this returns `transcript_url` — **not** the transcript text.

To get `full_transcript` without webhooks:

1. Call this endpoint after the job is terminal (filter with `status=COMPLETED`)
2. `GET` each `transcript_url` (no API key — pre-signed URL)
3. Read `full_transcript` from the JSON

`transcript_url` expires in **1 hour**. Re-call this endpoint for a fresh URL.

## Authentication

| Header | Required | Description |
| - | - | - |
| `X-API-Key-ID` | Yes | Your Gnani API key |

## Path parameters

> [!WARNING]
>
> In **Try it**, paste a real `job_id` from [Create job](https://docs.gnani.ai/api/STTBatch/Create_Job.md) before clicking Send. Leaving the placeholder `{job_id}` in the URL returns `422`.

**job\_id** `string` *required* (default: 019fa854-1db0-7e45-a026-7a6b09ff6d7c)

Job ID returned by [Create job](https://docs.gnani.ai/api/STTBatch/Create_Job.md). Replace with your own `job_id` before sending.

## Query parameters

**status** `string` (default: COMPLETED)

Filter by file status. Use `COMPLETED` for successful transcripts. Omit to include `FAILED` / `SKIPPED`.

**limit** `integer` (default: 50)

Page size (1–100).

**cursor** `string`

Pagination cursor from `pagination.next_cursor`.

## Example cURL

```bash theme={null}
curl --request GET \
  --url 'https://api.vachana.ai/stt/v3/batch/jobs/019fa79e-81f9-7a8a-a446-6eff16ddec30/files?status=COMPLETED' \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

Download transcript text:

```bash theme={null}
curl -L "<transcript_url_from_response>"
```

## Example — Python SDK

The SDK lists the files, downloads each `transcript_url`, and re-fetches the link if it has expired — you read `text` directly.

```python theme={null}
from gnani.stt import GnaniSTTBatchClient

client = GnaniSTTBatchClient()
job = client.get_job("<job_id>")

for f in job.files():                  # job.files(status="COMPLETED") to filter
    print(f.name, f.status, f.duration)
    if f.ok:
        print(f.text)                  # full_transcript
        for seg in f.segments:         # start, end, text, speaker
            print(f"[{seg.start:.1f}-{seg.end:.1f}] speaker {seg.speaker}: {seg.text}")
    else:
        print("failed:", f.error)

job.save("./outputs")                  # one JSON per completed file
```

See the [Python SDK](https://docs.gnani.ai/python-sdk/speech-to-text-batch.md#results).

## Response

### Success — completed file (`200`)

```json theme={null}
{
  "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
  "data": [
    {
      "file_id": "6f5e3bcd-add2-479c-8883-a9c27b221f10",
      "original_path": "customer_call.wav",
      "status": "COMPLETED",
      "duration_seconds": "6.01",
      "transcript_url": "https://gnaniasraudios.s3.amazonaws.com/results/019fa79e-81f9-7a8a-a446-6eff16ddec30/6f5e3bcd-add2-479c-8883-a9c27b221f10.json?X-Amz-Expires=3600&...",
      "error_message": null,
      "created_at": "2026-07-28T07:26:50.926489Z",
      "completed_at": "2026-07-28T07:27:24.513422Z"
    }
  ],
  "pagination": {
    "has_more": false,
    "next_cursor": null,
    "total_count": 1
  }
}
```

### Transcript document

The JSON behind `transcript_url`. It has the same keys for every model. Three fields are filled differently depending on the model:

| Field | Prisma v2.5 | Prisma v3.0 |
| - | - | - |
| `model` | the job's model | `"prisma-v3.0"` |
| `language_code` | the language that was identified (or the first code you sent) | **One code:** the code you sent. **`indic-auto` or several codes:** the language that covers the most speech in the file. |
| `segments[].language_detected` | set only for multi-language jobs that identify the language per speaker turn, otherwise `null` | **Set on every segment with text:** the language the model reported for that segment. `null` for a segment with no text. |

For Prisma v3.0, `language_detected` describes what the segment's text is **written in**. A Hindi speaker who answers in English is tagged `en-IN`. Hindi and Marathi share Devanagari, so a short Devanagari segment with nothing distinctive is tagged `hi-IN`, unless `mr-IN` is the only one of the two among the languages you sent.

#### Prisma v2.5

> [!NOTE]
>
> `language_code` here is the language the file was **actually transcribed in**. When you
> submit a comma-separated list, this is the single language that was identified — not the
> list you sent — so it always tells you what the text is in.

```json theme={null}
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
```

#### Prisma v3.0

```json theme={null}
{
  "file_id": "0192c8f5-1a2b-7c3d-8e4f-5a6b7c8d9e0f",
  "job_id": "0192c8f4-7c1e-7b3a-9f2d-5e8a1b7c4d21",
  "original_path": "s3://my-bucket/calls/call-1.wav",
  "language_code": "hi-IN",
  "duration_seconds": 184.32,
  "model": "prisma-v3.0",
  "mode": "transcribe",
  "segments": [
    {
      "segment_id": 0,
      "start_time": 0.42,
      "end_time": 6.18,
      "text": "नमस्ते, मैं HDFC Bank से बात कर रहा हूँ",
      "speaker_id": 0,
      "confidence": null,
      "language_detected": "hi-IN"
    },
    {
      "segment_id": 1,
      "start_time": 6.9,
      "end_time": 9.75,
      "text": "Yes, tell me, what is this regarding?",
      "speaker_id": 1,
      "confidence": null,
      "language_detected": "en-IN"
    },
    {
      "segment_id": 2,
      "start_time": 10.4,
      "end_time": 11.02,
      "text": "",
      "speaker_id": -1,
      "confidence": null,
      "language_detected": null
    }
  ],
  "full_transcript": "नमस्ते, मैं HDFC Bank से बात कर रहा हूँ Yes, tell me, what is this regarding?",
  "created_at": "2026-10-21T08:16:39Z",
  "engine": "go-batch-asr"
}
```

### Failed file — empty / non-speech audio

```json theme={null}
{
  "job_id": "019fa79b-a07a-7a3e-93bf-4ee73974dfa2",
  "data": [
    {
      "file_id": "e0323a1c-86ee-4898-aee7-7455dfc1eb52",
      "original_path": "customer_call.wav",
      "status": "FAILED",
      "duration_seconds": null,
      "transcript_url": null,
      "error_message": "Empty transcript after 3 retries",
      "created_at": "2026-07-28T07:23:42.170454Z",
      "completed_at": "2026-07-28T07:24:32.106034Z"
    }
  ],
  "pagination": {
    "has_more": false,
    "next_cursor": null,
    "total_count": 1
  }
}
```

### Skipped file — invalid public URL

```json theme={null}
{
  "job_id": "019fa79c-ec88-770c-b498-371fc21fb40e",
  "data": [
    {
      "file_id": "7539fecd-3090-4b62-9172-01c7019430d3",
      "original_path": "https://cdn.example.com/audio/missing.wav",
      "status": "SKIPPED",
      "duration_seconds": null,
      "transcript_url": null,
      "error_message": "REQUEST_ERROR: [Errno -2] Name or service not known",
      "created_at": "2026-07-28T07:27:27.650893Z",
      "completed_at": null
    }
  ],
  "pagination": {
    "has_more": false,
    "next_cursor": null,
    "total_count": 1
  }
}
```

| File status | Meaning |
| - | - |
| `COMPLETED` | Done — `transcript_url` available |
| `FAILED` | Failed — see `error_message` |
| `SKIPPED` | Not processed (bad URL / format / access) |
| `CANCELLED` | Skipped due to job cancel |

### File error codes

A file that ends in `FAILED` can carry an `error_code`.

| `error_code` | Meaning |
| - | - |
| `INVALID_RECOGNITION_OPTIONS` | **Prisma v3.0.** The speech service refused the job's `format`, `keyterms`, `topic` or `speaker_names` (for example, because context is switched off in that deployment). Every segment would be refused the same way, so the file fails at once. |
| `UNSUPPORTED_LANGUAGE` | The model refused a language. This also covers its `MODEL_UNSUPPORTED_LANGUAGE`. |

All other file errors are unchanged.

### File stages

For a `prisma-v3.0` job, a file's `stage` goes `ingest → transcode → [denoise] → sad → diarize → recognize → assemble`.

**data\[].transcript\_url** `string`

Pre-signed URL to transcript JSON. Expires in 1 hour. No API key required to download.

**data\[].error\_message** `string`

Present when `status` is `FAILED` or `SKIPPED`.

## Use cases

* Fetching transcript download links after a job completes
* Inspecting failed / skipped files via `error_message`


## OpenAPI

````yaml STTBatch.yml GET /stt/v3/batch/jobs/{job_id}/files
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
  /stt/v3/batch/jobs/{job_id}/files:
    get:
      tags:
        - Speech-to-Text (Batch)
      summary: Get Job Files
      description: >
        List per-file results and transcript URLs. Returns URLs, not transcript
        text.

        Call after a terminal job status, then GET each transcript_url.
      operationId: list_batch_job_files
      parameters:
        - $ref: '#/components/parameters/JobId'
        - name: status
          in: query
          required: false
          description: Filter by file status (e.g. COMPLETED)
          schema:
            type: string
          example: COMPLETED
        - name: limit
          in: query
          required: false
          description: Page size (1–100)
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 50
          example: 50
        - name: cursor
          in: query
          required: false
          description: Pagination cursor from pagination.next_cursor
          schema:
            type: string
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
              example:
                job_id: 019fa79e-81f9-7a8a-a446-6eff16ddec30
                data:
                  - file_id: a5708e96-7a28-4c01-8b07-2fe606fa9785
                    original_path: customer_call.wav
                    status: COMPLETED
                    duration_seconds: '6.01'
                    transcript_url: https://example-presigned-url.example/transcript.json
                    error_message: null
                pagination:
                  has_more: false
                  next_cursor: null
                  total_count: 1
components:
  parameters:
    JobId:
      name: job_id
      in: path
      required: true
      description: >-
        Job ID returned by Create Job. Paste the UUID from the Create Job
        response.
      schema:
        type: string
        default: 019fa854-1db0-7e45-a026-7a6b09ff6d7c
      example: 019fa854-1db0-7e45-a026-7a6b09ff6d7c
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key-ID
      description: Your Gnani API key

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.