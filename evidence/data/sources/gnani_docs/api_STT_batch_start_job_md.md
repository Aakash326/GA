> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Start Job

> Start processing a batch transcription job.

## Overview

Start transcription for a job in `CREATED` status. Returns `202 Accepted` while validation and queueing run in the background.

Creating a job does **not** start processing — you must call this endpoint.

## Authentication

| Header | Required | Description |
| - | - | - |
| `X-API-Key-ID` | Yes | Your Gnani Prisma v2.5 API key |

## Path Parameters

**job\_id** `string` *required*

Job ID returned by **Create Job**.

## Example cURL

```bash theme={null}
curl -X POST "https://api.vachana.ai/stt/v3/batch/jobs/019fa259-b084-71eb-94d7-ba4cdf2e64c6/start" \
  -H "X-API-Key-ID: <YOUR_API_KEY>"
```

## Response

### Success (202)

```json theme={null}
{
  "job_id": "019fa259-b084-71eb-94d7-ba4cdf2e64c6",
  "status": "STARTING",
  "message": "Job start accepted. File validation and queueing are running in the background. Poll GET /stt/v3/batch/jobs/{job_id} to track progress."
}
```

### Error responses

**409 Already started**

```json theme={null}
{
  "error": "JOB_ALREADY_STARTED",
  "message": "Job cannot be restarted from state 'COMPLETED'"
}
```

## Use Cases

* Kicking off transcription after files are uploaded
* Starting a public-URL job after create (URL validation happens at start)

Next: poll **Get Job Status** every 10 seconds (30 seconds for 100+ file jobs) until a terminal status.


## OpenAPI

````yaml POST /stt/v3/batch/jobs/{job_id}/start
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