> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Cancel job

> Cancel a batch transcription job.

## Overview

Part of [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md), which covers the whole flow, models, languages and limits.

Cancel a batch job that is not already in a conflicting terminal state.

| Current status | Result |
| - | - |
| `CREATED` | Immediately `CANCELLED` (`200`) |
| `STARTING` / `QUEUED` / `IN_PROGRESS` | `CANCELLING` → `CANCELLED` |
| Already `CANCELLED` | `409 JOB_CANCELLED` |
| Other terminal states | Conflict error |

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

## Request body

**reason** `string` (default: Docs verification cancel test)

Optional cancel reason.

## Example cURL

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3/batch/jobs/019fa79c-7880-7d05-a528-edc7892ad9ea/cancel \
  --header 'X-API-Key-ID: <YOUR_API_KEY>' \
  --header 'Content-Type: application/json' \
  --data '{"reason":"Docs verification cancel test"}'
```

## Example — Python SDK

```python theme={null}
from gnani.stt import GnaniSTTBatchClient

client = GnaniSTTBatchClient()

job = client.get_job("<job_id>")
job.cancel(reason="uploaded the wrong files")
print(job.status)                      # CANCELLING or CANCELLED
```

See the [Python SDK](https://docs.gnani.ai/python-sdk/speech-to-text-batch.md#list-and-cancel-jobs).

## Response

### Success (`200`)

```json theme={null}
{
  "job_id": "019fa79c-7880-7d05-a528-edc7892ad9ea",
  "status": "CANCELLED",
  "message": "Job cancelled successfully.",
  "cancelled_at": "2026-07-28T07:24:38.366982Z"
}
```

### Error responses

**409 Already cancelled**

```json theme={null}
{
  "error": "JOB_CANCELLED",
  "message": "Job is already cancelled"
}
```

**404 Job not found**

```json theme={null}
{
  "error": "JOB_NOT_FOUND",
  "message": "Job 01900000-0000-7000-8000-000000000000 not found"
}
```

**409 Already finished**

```json theme={null}
{
  "error": "JOB_ALREADY_COMPLETED",
  "message": "Job has already finished with status 'COMPLETED'"
}
```

**status** `string`

`CANCELLED` on success.

**cancelled\_at** `string`

Timestamp when the job was cancelled.

## Use cases

* Cancelling a job before start when files were uploaded by mistake
* Stopping an in-progress batch when the pipeline is aborted


## OpenAPI

````yaml STTBatch.yml POST /stt/v3/batch/jobs/{job_id}/cancel
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
  /stt/v3/batch/jobs/{job_id}/cancel:
    post:
      tags:
        - Speech-to-Text (Batch)
      summary: Cancel Job
      description: Cancel a batch job that is not already in a conflicting terminal state.
      operationId: cancel_batch_job
      parameters:
        - $ref: '#/components/parameters/JobId'
      requestBody:
        required: false
        content:
          application/json:
            schema:
              type: object
              properties:
                reason:
                  type: string
                  description: Optional cancel reason
                  example: Docs verification cancel test
            example:
              reason: Docs verification cancel test
      responses:
        '200':
          description: Cancelled
          content:
            application/json:
              schema:
                type: object
              example:
                job_id: 019fa79c-7880-7d05-a528-edc7892ad9ea
                status: CANCELLED
                message: Job cancelled successfully.
                cancelled_at: '2026-07-28T07:24:38.366982Z'
        '409':
          description: Already cancelled or conflicting state
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