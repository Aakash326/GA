> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Error Reference

> HTTP status codes and known error messages for the Agent Builder Platform API

**What it does:** Reference all error types returned by the Agent Builder Platform API. All error responses follow the standard envelope format:

```json theme={null}
{
  "status": "failure",
  "requestId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Human-readable error description."
}
```

> [!NOTE]
>
> When contacting Gnani support, always include the **`requestId`** from the error response. This UUID uniquely identifies the failed request in the platform logs and allows the engineering team to diagnose the issue quickly.

***

## HTTP Status Codes

| Status Code | Name | When It Occurs |
| - | - | - |
| **200** | OK | The request was successful. |
| **201** | Created | A new resource (agent, FAQ) was created successfully. |
| **400** | Bad Request | The request body or query parameters are invalid, missing required fields, or fail a business rule (e.g. FAQ limit reached, incompatible ASR model). |
| **401** | Unauthorized | The API key is missing, invalid, or expired. |
| **403** | Forbidden | The API key is valid but does not have the required permission for this endpoint, or the user role (e.g. QA) does not have write access. |
| **404** | Not Found | The requested resource does not exist — unknown or inaccessible `botId`, conversation ID, FAQ entry, audio recording, or invalid config path (e.g. unknown region ID, transcriber language). |
| **409** | Conflict | A resource with the same name already exists (e.g. duplicate agent name). |
| **429** | Too Many Requests | The request rate limit has been exceeded. Wait before retrying. |
| **500** | Internal Server Error | An unexpected error occurred on the Agent Builder platform. Retry the request. If the error persists, contact support with the `requestId`. |

***

## Known Error Messages

The table below lists the specific error messages returned in the `message` field of the JSON response body, along with the HTTP status code and the condition that triggers each one.

| Status | Error Message | Condition |
| - | - | - |
| `400` | `Maximum 3 languages are allowed` | `botDetails.language` contains more than 3 language codes. |
| `400` | `At least one language is required` | `botDetails.language` is empty. |
| `400` | `Unsupported language(s): [...]. Please use /platform/v1/agents/config/languages` | One or more language codes are not in the supported list. |
| `400` | `Selected ASR provider does not support selected languages. Please check /platform/v1/agents/config/transcriber_config` | The chosen ASR provider is incompatible with one or more selected languages. |
| `400` | `Selected ASR model does not support selected languages. Please check /platform/v1/agents/config/transcriber_config` | The chosen ASR model is incompatible with one or more selected languages. |
| `400` | `Selected TTS provider does not support selected languages. Please check /platform/v1/agents/config/tts_config` | The chosen TTS provider is incompatible with one or more selected languages. |
| `400` | `Selected TTS voice does not support selected languages. Please check /platform/v1/agents/config/tts_config` | The chosen TTS voice is incompatible with one or more selected languages. |
| `400` | ``Field `phraseConfig.phrase` exceeds maximum of 100 entries.`` | The custom vocabulary list contains more than 100 phrases. |
| `400` | ``Field `phraseConfig` is not supported for ASR model `{model}`.`` | Custom vocabulary was sent for an ASR model that does not support it. |
| `400` | ``Field `speechSegmentationSilenceTimeout` is not supported for ASR model `{model}`.`` | The field was sent for an incompatible ASR model. |
| `400` | ``Field `speechInitialSilenceTimeout` value {v} exceeds maximum of {max} seconds for ASR model `{model}`.`` | `speechInitialSilenceTimeout` exceeds the 30-second limit for streaming ASR models. |
| `400` | ``Field `minWordsForBargeIn` is not supported for non-streaming ASR model `{model}`.`` | The field was sent for a REST (non-streaming) ASR model. |
| `400` | ``Field `minTimeToBarge` is not supported for streaming ASR model `{model}`.`` | The field was sent for a streaming ASR model. |
| `400` | ``Field `asrPreemptive` (Fast Streaming) is not supported for ASR model `{model}`.`` | The field was sent for an ASR model that does not support fast streaming. |
| `400` | `languageSwitchMode must be 'implicit' or 'explicit'` | An invalid `languageSwitchMode` value was provided. |
| `400` | `minWordsForLangSwitch must be >= 1` | The `minWordsForLangSwitch` value is less than 1. |
| `403` | `QA role does not have permission to create/update agents` | The API key is associated with a user in the QA role. |
| `404` | `Agent not found or does not belong to your organization` | The `botId` does not exist or is not accessible to your API key. Returned by Get, Update, and Delete Agent. |
| `404` | `Agent not found` | The `botId` does not exist or is not accessible. Returned by FAQ and Chat SDK endpoints scoped to an agent. |
| `404` | `Conversation not found` | The `conversationId` does not exist or is not accessible. |
| `404` | `Audio file not found at path: ...` | No recording exists for this conversation (recording disabled, call too short, or file not yet available). |
| `409` | `An agent named '...' already exists in your organization` | A duplicate agent name was used on create or rename. |

***

## Handling Errors in Code

### Example: Check Status and Handle Errors

```javascript theme={null}
const response = await fetch(
  'https://api.inya.ai/platform/v1/agents',
  {
    method: 'POST',
    headers: {
      'x-api-key': '<your_api_key>',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ botName: 'Support Agent', region: 'asia', timeZone: 'Asia/Kolkata' })
  }
);

const body = await response.json();

if (body.status !== 'success') {
  console.error(`Request failed [${body.requestId}]: ${body.message}`);
  // Store body.requestId for support escalation
}
```

```python theme={null}
import requests

response = requests.post(
  'https://api.inya.ai/platform/v1/agents',
  headers={'x-api-key': '<your_api_key>'},
  json={'botName': 'Support Agent', 'region': 'asia', 'timeZone': 'Asia/Kolkata'}
)

body = response.json()
if body.get('status') != 'success':
    print(f"Request failed [{body.get('requestId')}]: {body.get('message')}")
    # Store body['requestId'] for support escalation
```

***

## Rate Limits

The Platform API enforces rate limits to ensure fair usage. When exceeded, the API returns **HTTP 429**. Implement exponential backoff in your retry logic:

```python theme={null}
import time

def call_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        response = func()
        if response.status_code != 429:
            return response
        wait = 2 ** attempt  # 1s, 2s, 4s
        print(f"Rate limited. Retrying in {wait}s...")
        time.sleep(wait)
    raise Exception("Max retries exceeded")
```

> [!TIP]
>
> Store the `requestId` from every API response in your application logs. This makes it straightforward to correlate your own logs with Agent Builder platform logs when troubleshooting.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.