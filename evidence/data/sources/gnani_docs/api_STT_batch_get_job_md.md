> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Job Status

> Get batch job status and progress counters.

## Overview

Get the current status and progress of a batch job.

This response does **not** include transcript text. After a terminal status, call **Get Job Files**, then `GET` each `transcript_url`.

## Authentication

| Header | Required | Description |
| - | - | - |
| `X-API-Key-ID` | Yes | Your Gnani Prisma v2.5 API key |

## Path Parameters

**job\_id** `string` *required*

Job ID returned by **Create Job**.

## Polling guidance

| Status | Terminal | Next step |
| - | - | - |
| `COMPLETED` | Yes | Call `/files`, then GET each `transcript_url` |
| `PARTIAL_FAILURE` | Yes | Same — fetch successful files via `/files` |
| `FAILED` | Yes | Inspect `/files` + `error_message` |
| `START_FAILED` | Yes | Read `cancel_reason` |
| `CANCELLED` | Yes | Done |

Poll no faster than every **10 seconds**. For 100+ file jobs, prefer every **30 seconds**.

`config` echoes what the job was created with. `bias_list` and `bias_score` are `null` unless word boosting was requested.

## Example cURL

```bash theme={null}
curl "https://api.vachana.ai/stt/v3/batch/jobs/019fa259-b084-71eb-94d7-ba4cdf2e64c6" \
  -H "X-API-Key-ID: <YOUR_API_KEY>"
```

## Response

### Success (200)

```json theme={null}
{
  "job_id": "019fa259-b084-71eb-94d7-ba4cdf2e64c6",
  "status": "COMPLETED",
  "config": {
    "model": "prisma-v2.5",
    "mode": "transcribe",
    "language_code": "en-IN",
    "with_diarization": false,
    "num_speakers": null,
    "is_multi_channel": false,
    "bias_list": null,
    "bias_score": null
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
  "created_at": "2026-07-27T06:53:34.750193Z",
  "started_at": "2026-07-27T06:53:37.276061Z",
  "completed_at": "2026-07-27T06:53:52.179794Z",
  "cancelled_at": null,
  "updated_at": "2026-07-27T06:53:52.179928Z"
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

## Use Cases

* Polling until a job reaches a terminal status
* Checking progress counters for multi-file jobs

Next: call **Get Job Files** with `status=COMPLETED`.


## OpenAPI

````yaml GET /stt/v3/batch/jobs/{job_id}
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