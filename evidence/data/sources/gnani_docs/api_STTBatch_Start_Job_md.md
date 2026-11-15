> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Start job

> Start processing a batch transcription job.

## Overview

Part of [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md), which covers the whole flow, models, languages and limits.

Start transcription for a job in `CREATED` status. Returns `202 Accepted` while validation and queueing run in the background.

Creating a job does **not** start processing — you must call this endpoint.

For public-URL jobs, path validation happens here. If every path fails, status becomes `START_FAILED`.

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

## Example cURL

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs/019fa79e-81f9-7a8a-a446-6eff16ddec30/start \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

## Example — Python SDK

```python theme={null}
from gnani.stt import GnaniSTTBatchClient

client = GnaniSTTBatchClient()

job = client.get_job("<job_id>")   # or the job returned by create_job(start=False)
job.start()
print(job.status)                  # STARTING
```

`client.create_job(...)` already starts the job unless you pass `start=False`, so most programs never call `start()`. See the [Python SDK](https://docs.gnani.ai/python-sdk/speech-to-text-batch.md).

## Response

### Success (`202`)

```json theme={null}
{
  "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
  "status": "STARTING",
  "message": "Job start accepted. File validation and queueing are running in the background. Poll GET /stt/v3/batch/jobs/{job_id} to track progress."
}
```

### Error responses

**409 Already started / finished**

```json theme={null}
{
  "error": "JOB_ALREADY_STARTED",
  "message": "Job cannot be restarted from state 'FAILED'"
}
```

**404 Job not found**

```json theme={null}
{
  "error": "JOB_NOT_FOUND",
  "message": "Job 01900000-0000-7000-8000-000000000000 not found"
}
```

**409 Cancelled before starting**

```json theme={null}
{
  "error": "JOB_CANCELLED",
  "message": "Job was cancelled before starting"
}
```

**job\_id** `string`

Job identifier.

**status** `string`

Typically `STARTING` after a successful start.

## Use cases

* Kicking off transcription after files are uploaded
* Starting a public-URL job after create

Next: poll [Get job status](https://docs.gnani.ai/api/STTBatch/Get_Job.md) every **10 seconds** (prefer **30 seconds** for 100+ file jobs).


## OpenAPI

````yaml STTBatch.yml POST /stt/v3/batch/jobs/{job_id}/start
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
  /stt/v3/batch/jobs/{job_id}/start:
    post:
      tags:
        - Speech-to-Text (Batch)
      summary: Start Job
      description: >-
        Start processing a job in CREATED status. Returns 202 while
        validation/queueing run.
      operationId: start_batch_job
      parameters:
        - $ref: '#/components/parameters/JobId'
      responses:
        '202':
          description: Accepted
          content:
            application/json:
              schema:
                type: object
              example:
                job_id: 019fa79e-81f9-7a8a-a446-6eff16ddec30
                status: STARTING
                message: >-
                  Job start accepted. File validation and queueing are running
                  in the background. Poll GET /stt/v3/batch/jobs/{job_id} to
                  track progress.
        '409':
          description: Job already started or in a terminal state
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