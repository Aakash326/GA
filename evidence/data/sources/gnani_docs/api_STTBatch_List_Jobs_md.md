> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# List jobs

> List batch transcription jobs with optional status filter and pagination.

## Overview

Part of [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md), which covers the whole flow, models, languages and limits.

List batch jobs for your organization. Use filters and cursor pagination to browse history.

## Authentication

| Header | Required | Description |
| - | - | - |
| `X-API-Key-ID` | Yes | Your Gnani API key |

## Query parameters

**status** `string`

Return only jobs with this status. Each value is described in [Job statuses](https://docs.gnani.ai/api/STTBatch/Introduction.md#job-statuses).

| Value | Meaning |
| - | - |
| `CREATED` | Waiting for `/start` |
| `STARTING` | Setup running |
| `QUEUED` | Files queued |
| `IN_PROGRESS` | Transcription running |
| `COMPLETED` | All files succeeded |
| `PARTIAL_FAILURE` | Mixed results |
| `FAILED` | Failed |
| `START_FAILED` | Setup failed |
| `CANCELLING` | Cancel in progress |
| `CANCELLED` | Cancelled |

**limit** `integer` (default: 20)

Page size (1–100).

**cursor** `string`

Pagination cursor from `pagination.next_cursor`.

## Example cURL

```bash theme={null}
curl --request GET \
  --url 'https://api.vachana.ai/stt/v3/batch/jobs?limit=3' \
  --header 'X-API-Key-ID: <YOUR_API_KEY>'
```

## Example — Python SDK

`list_jobs()` follows cursor pagination for you.

```python theme={null}
from gnani.stt import GnaniSTTBatchClient

client = GnaniSTTBatchClient()

for job in client.list_jobs(status="COMPLETED", limit=20):
    print(job.id, job.status, job.completed_files, "/", job.total_files)
```

`limit` is the page size (1–100). Async: `async for job in AsyncGnaniSTTBatchClient().list_jobs(): ...`. See the [Python SDK](https://docs.gnani.ai/python-sdk/speech-to-text-batch.md#list-and-cancel-jobs).

## Response

### Success (`200`)

```json theme={null}
{
  "data": [
    {
      "job_id": "019fa79e-81f9-7a8a-a446-6eff16ddec30",
      "status": "COMPLETED",
      "total_files": 1,
      "completed_files": 1,
      "failed_files": 0,
      "created_at": "2026-07-28T07:26:50.926489Z",
      "completed_at": "2026-07-28T07:27:24.621462Z"
    },
    {
      "job_id": "019fa79b-a07a-7a3e-93bf-4ee73974dfa2",
      "status": "FAILED",
      "total_files": 1,
      "completed_files": 0,
      "failed_files": 1,
      "created_at": "2026-07-28T07:23:42.170454Z",
      "completed_at": "2026-07-28T07:24:32.176627Z"
    }
  ],
  "pagination": {
    "has_more": true,
    "next_cursor": "eyJjcmVhdGVkX2F0IjogIjIwMjYtMDctMjdUMDc6NDM6NTguMDU1NzMzKzAwOjAwIiwgImlkIjogIjAxOWZhMjg3LWNmNjItNzE2OC1iM2MyLTQ1ZjExOGFjNzYxZCJ9"
  }
}
```

**data** `array`

List of jobs with status and file counters.

**data\[].total\_files** `integer`

Total files known for the job. May be `0` while still in `CREATED`.

**pagination.has\_more** `boolean`

Whether another page exists.

**pagination.next\_cursor** `string`

Pass as `cursor` on the next request.

## Use cases

* Reviewing recent batch jobs in your org
* Filtering failed or in-progress jobs for ops dashboards


## OpenAPI

````yaml STTBatch.yml GET /stt/v3/batch/jobs
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
    get:
      tags:
        - Speech-to-Text (Batch)
      summary: List Jobs
      description: List batch jobs with optional status filter and cursor pagination.
      operationId: list_batch_jobs
      parameters:
        - name: status
          in: query
          required: false
          description: >-
            Filter by job status (CREATED, IN_PROGRESS, COMPLETED, FAILED,
            CANCELLED, etc.)
          schema:
            type: string
        - name: limit
          in: query
          required: false
          description: Page size (1–100)
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
          example: 20
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
                data:
                  - job_id: 019fa79e-81f9-7a8a-a446-6eff16ddec30
                    status: COMPLETED
                    total_files: 1
                    completed_files: 1
                    failed_files: 0
                    created_at: '2026-07-28T07:26:50.926489Z'
                    completed_at: '2026-07-28T07:27:24.621462Z'
                pagination:
                  has_more: true
                  next_cursor: >-
                    eyJjcmVhdGVkX2F0IjogIjIwMjYtMDctMjdUMDc6NDM6NTguMDU1NzMzKzAwOjAwIiwgImlkIjogIjAxOWZhMjg3LWNmNjItNzE2OC1iM2MyLTQ1ZjExOGFjNzYxZCJ9
components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key-ID
      description: Your Gnani API key

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.