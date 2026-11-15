> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Get job status

> Get batch job status and progress counters.

## Overview

Part of [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md), which covers the whole flow, models, languages and limits.

Get the current status and progress of a batch job.

This response does **not** include transcript text. After a terminal status, call [Get job files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md), then `GET` each `transcript_url`.

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

## Polling guidance

Live lifecycle observed:

```text theme={null}
CREATED → STARTING → QUEUED → IN_PROGRESS → COMPLETED
```

| Status | Terminal | Next step |
| - | - | - |
| `COMPLETED` | Yes | Call `/files`, then GET each `transcript_url` |
| `PARTIAL_FAILURE` | Yes | Same — fetch successful files via `/files` |
| `FAILED` | Yes | Inspect `/files` + `error_message` |
| `START_FAILED` | Yes | Read `cancel_reason` |
| `CANCELLED` | Yes | Done |

Poll no faster than every **10 seconds**. For 100+ file jobs, prefer every **30 seconds**.

## Example cURL

```bash theme={null}
curl --request GET \
  --url https://api.vachana.ai/stt/v3/batch/jobs/019fa79e-81f9-7a8a-a446-6eff16ddec30 \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

## Example — Python SDK

```python theme={null}
from gnani.stt import GnaniSTTBatchClient

client = GnaniSTTBatchClient()

job = client.get_job("<job_id>")
print(job.status, job.percent)                       # IN_PROGRESS 42
print(job.completed_files, "/", job.total_files)
```

To block until the job finishes, use `job.wait()`. It polls every 10 seconds, the minimum this page recommends:

```python theme={null}
job.wait(timeout=3600, on_progress=lambda j: print(j.status, j.percent))
```

`wait()` returns for `COMPLETED` and `PARTIAL_FAILURE`, and raises `BatchJobFailedError` for `FAILED`, `START_FAILED`, and `CANCELLED`. See the [Python SDK](https://docs.gnani.ai/python-sdk/speech-to-text-batch.md#waiting-for-a-job).

## Response

### Success — completed (`200`)

```json theme={null}
{
  "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
  "status": "COMPLETED",
  "config": {
    "model": "prisma-v2.5",
    "mode": "transcribe",
    "language_code": "en-IN",
    "with_diarization": false,
    "num_speakers": null,
    "is_multi_channel": false,
    "with_denoise": false,
    "format": null,
    "keyterms": null,
    "topic": null,
    "speaker_names": null
  },
  "progress": {
    "total_files": 1,
    "completed_files": 1,
    "failed_files": 0,
    "in_progress_files": 0,
    "queued_files": 0,
    "cancelled_files": 0
  },
  "cancel_reason": null,
  "created_at": "2026-07-28T07:26:50.926489Z",
  "started_at": "2026-07-28T07:26:52.421366Z",
  "completed_at": "2026-07-28T07:27:24.621462Z",
  "cancelled_at": null,
  "updated_at": "2026-07-28T07:27:24.621676Z"
}
```

### Success — Prisma v3.0 job (`200`)

For a `prisma-v3.0` job, `config` echoes the Prisma v3.0 options:

```json theme={null}
{
  "job_id": "0192c8f4-7c1e-7b3a-9f2d-5e8a1b7c4d21",
  "status": "IN_PROGRESS",
  "config": {
    "model": "prisma-v3.0",
    "mode": "transcribe",
    "language_code": "hi-IN,en-IN",
    "with_diarization": true,
    "num_speakers": 2,
    "is_multi_channel": false,
    "with_denoise": false,
    "bias_list": null,
    "bias_score": null,
    "format": "transcribe",
    "keyterms": ["HDFC Bank", "EMI", "खाता नंबर"],
    "topic": "Loan collection calls for a retail credit card portfolio",
    "speaker_names": null
  },
  "progress": {
    "total_files": 3,
    "completed_files": 1,
    "failed_files": 0,
    "in_progress_files": 0,
    "queued_files": 2,
    "cancelled_files": 0,
    "percent": 41
  },
  "cancel_reason": null,
  "created_at": "2026-10-21T08:15:02.481Z",
  "started_at": "2026-10-21T08:15:09.120Z",
  "completed_at": null,
  "cancelled_at": null,
  "updated_at": "2026-10-21T08:16:40.002Z"
}
```

`format`, `keyterms`, `topic` and `speaker_names` are on every job's `config`, and are `null` for jobs on other models. With `prisma-v3.0`, `language_code` is the value you sent (`"indic-auto"` is stored as `"auto"`), and `bias_list` sent as the older name of `keyterms` shows up in `keyterms`, with `bias_list` and `bias_score` `null`.

### Success — start failed (`200`)

Returned when public URLs cannot be fetched:

```json theme={null}
{
  "job_id": "019fa79c-ec88-770c-b498-371fc21fb40e",
  "status": "START_FAILED",
  "config": {
    "model": "prisma-v2.5",
    "mode": "transcribe",
    "language_code": "en-IN",
    "with_diarization": false,
    "num_speakers": null,
    "is_multi_channel": false,
    "with_denoise": false,
    "format": null,
    "keyterms": null,
    "topic": null,
    "speaker_names": null
  },
  "progress": {
    "total_files": 0,
    "completed_files": 0,
    "failed_files": 0,
    "in_progress_files": 0,
    "queued_files": 0,
    "cancelled_files": 0
  },
  "cancel_reason": "All provided paths were invalid — nothing to process.",
  "created_at": "2026-07-28T07:25:07.137907Z",
  "started_at": null,
  "completed_at": null,
  "cancelled_at": null,
  "updated_at": "2026-07-28T07:27:28.390415Z"
}
```

### Error responses

**404 Job not found**

```json theme={null}
{
  "error": "JOB_NOT_FOUND",
  "message": "Job 01900000-0000-7000-8000-000000000000 not found"
}
```

**status** `string`

Current job status (`CREATED`, `QUEUED`, `IN_PROGRESS`, `COMPLETED`, `START_FAILED`, …).

**progress** `object`

Per-file counters: total, completed, failed, in progress, queued, cancelled. `percent` is the overall progress, 0–100.

**cancel\_reason** `string`

Present for failures such as `START_FAILED`.

**config** `object`

The config the job was created with, echoed back — including `language_code`,
`with_diarization`, `with_denoise`, and `bias_list` / `bias_score` when set. It also
includes `format`, `keyterms`, `topic` and `speaker_names`, which are `null` unless the
job uses `prisma-v3.0`.

## Use cases

* Polling until a job reaches a terminal status
* Debugging `START_FAILED` via `cancel_reason`

Next: [Get job files](https://docs.gnani.ai/api/STTBatch/Get_Job_Files.md)


## OpenAPI

````yaml STTBatch.yml GET /stt/v3/batch/jobs/{job_id}
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
  /stt/v3/batch/jobs/{job_id}:
    get:
      tags:
        - Speech-to-Text (Batch)
      summary: Get Job Status
      description: >-
        Get batch job status and progress counters. Does not include transcript
        text.
      operationId: get_batch_job
      parameters:
        - $ref: '#/components/parameters/JobId'
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
              example:
                job_id: 019fa79e-81f9-7a8a-a446-6eff16ddec30
                status: COMPLETED
                config:
                  model: prisma-v2.5
                  mode: transcribe
                  language_code: en-IN
                  with_diarization: false
                  num_speakers: null
                  is_multi_channel: false
                  with_denoise: false
                  format: null
                  keyterms: null
                  topic: null
                  speaker_names: null
                progress:
                  total_files: 1
                  completed_files: 1
                  failed_files: 0
                  in_progress_files: 0
                  queued_files: 0
                  cancelled_files: 0
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