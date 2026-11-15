> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# List Jobs

> List batch transcription jobs with optional status filter and pagination.

## Overview

List batch jobs for your organization. Use filters and cursor pagination to browse history.

## Authentication

| Header | Required | Description |
| - | - | - |
| `X-API-Key-ID` | Yes | Your Gnani Prisma v2.5 API key |

## Query Parameters

**status** `string`

Filter by job status (`CREATED`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, etc.).

**limit** `integer` (default: 20)

Page size (1–100).

**cursor** `string`

Pagination cursor from `pagination.next_cursor`.

## Example cURL

```bash theme={null}
curl "https://api.vachana.ai/stt/v3/batch/jobs?limit=5" \
  -H "X-API-Key-ID: <YOUR_API_KEY>"
```

## Response

### Success (200)

```json theme={null}
{
  "data": [
    {
      "job_id": "019fa259-b084-71eb-94d7-ba4cdf2e64c6",
      "status": "COMPLETED",
      "total_files": 1,
      "created_at": "2026-07-27T06:53:34.750193Z",
      "completed_at": "2026-07-27T06:53:52.179794Z"
    }
  ],
  "pagination": {
    "has_more": false,
    "next_cursor": null,
    "total_count": 1
  }
}
```

## Use Cases

* Reviewing recent batch jobs in your org
* Filtering failed or in-progress jobs for ops dashboards


## OpenAPI

````yaml GET /stt/v3/batch/jobs
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