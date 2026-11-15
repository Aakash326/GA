> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Get Job Files

> List per-file results and transcript URLs for a batch job.

## Overview

List per-file results for a job. For completed files, this returns `transcript_url` — **not** the transcript text.

To get `full_transcript` without webhooks:

1. Call this endpoint after the job is terminal (filter with `status=COMPLETED`)
2. `GET` each `transcript_url` (no API key — pre-signed URL)
3. Read `full_transcript` from the JSON

`transcript_url` expires in **1 hour**. Re-call this endpoint for a fresh URL.

## Authentication

| Header | Required | Description |
| - | - | - |
| `X-API-Key-ID` | Yes | Your Gnani Prisma v2.5 API key |

## Path Parameters

**job\_id** `string` *required*

Job ID returned by **Create Job**.

## Query Parameters

**status** `string`

Filter by file status. Use `COMPLETED` to fetch successful transcripts.

**limit** `integer` (default: 50)

Page size (1–100).

**cursor** `string`

Pagination cursor from `pagination.next_cursor`.

## Example cURL

```bash theme={null}
curl "https://api.vachana.ai/stt/v3/batch/jobs/019fa259-b084-71eb-94d7-ba4cdf2e64c6/files?status=COMPLETED" \
  -H "X-API-Key-ID: <YOUR_API_KEY>"
```

Download transcript text:

```bash theme={null}
curl -L "<transcript_url_from_response>"
```

## Response

### Success (200)

```json theme={null}
{
  "job_id": "019fa259-b084-71eb-94d7-ba4cdf2e64c6",
  "data": [
    {
      "file_id": "28255118-03ca-48c5-807e-8d07a6f54d54",
      "original_path": "customer_call.wav",
      "status": "COMPLETED",
      "duration_seconds": "6.01",
      "transcript_url": "https://gnaniasraudios.s3.amazonaws.com/results/example.json?X-Amz-Expires=3600",
      "error_message": null,
      "created_at": "2026-07-27T06:53:34.750193Z",
      "completed_at": "2026-07-27T06:53:52.128197Z"
    }
  ],
  "pagination": {
    "has_more": false,
    "next_cursor": null,
    "total_count": 1
  }
}
```

### transcript\_url JSON

```json theme={null}
{
  "file_id": "28255118-03ca-48c5-807e-8d07a6f54d54",
  "job_id": "019fa259-b084-71eb-94d7-ba4cdf2e64c6",
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
      "speaker_id": 1
    }
  ],
  "full_transcript": "hello how can i help you today i am calling about my recent order number 12345",
  "created_at": "2026-07-27T06:53:52Z"
}
```

## Use Cases

* Fetching transcript download links after a job completes
* Inspecting failed / skipped files via `error_message`


## OpenAPI

````yaml GET /stt/v3/batch/jobs/{job_id}/files
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