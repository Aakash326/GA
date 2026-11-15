> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Get LLM Models

> Retrieve available Large Language Model providers and models for agent configuration

**What it does:** Retrieve all available LLM (Large Language Model) providers and their supported models. The LLM is the reasoning engine of your agent — it processes user input, maintains conversation context, and generates responses based on the system prompt. Use this endpoint to populate model selection options when configuring an agent's `llmParams`.

## Required Permission

`agents`

## Query Parameters

| Name | Type | Required | Description |
| - | - | - | - |
| `provider` | string | No | Filter results to a specific LLM provider (e.g. `gnani`, `openai`). When omitted, all available providers and models are returned. |

## Minimum working example

```bash theme={null}
curl "https://api.inya.ai/platform/v1/agents/config/llm_models" \
  -H "x-api-key: <your_api_key>"
```

## Additional examples

### Filter by Provider

```bash theme={null}
curl "https://api.inya.ai/platform/v1/agents/config/llm_models?provider=gnani" \
  -H "x-api-key: <your_api_key>"
```

## Response

### Success (200)

```json theme={null}
{
  "status": "success",
  "requestId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Models retrieved successfully",
  "response": {
    "LLM": [
      {
        "name": "Anthropic",
        "provider": {
          "providerId": "anthropic",
          "label": "Anthropic",
          "functionCalling": true,
          "multilingual": true
        },
        "models": [
          {
            "modelId": "claude-3-5-sonnet-20241022",
            "label": "Claude-3-5-Sonnet",
            "functionCalling": true,
            "supportedLanguages": ["en-IN", "hi-IN", "ta-IN", "kn-IN", "en-US"]
          }
        ]
      },
      {
        "name": "Gnani",
        "provider": {
          "providerId": "gnani",
          "label": "Gnani",
          "functionCalling": true,
          "multilingual": true
        },
        "models": [
          {
            "modelId": "Pampa Go",
            "label": "Pampa Go",
            "functionCalling": true,
            "supportedLanguages": ["en-IN", "hi-IN", "ta-IN", "kn-IN", "en-US"]
          },
          {
            "modelId": "Pampa Priority",
            "label": "Pampa Priority",
            "functionCalling": true,
            "supportedLanguages": ["en-IN", "hi-IN", "ta-IN", "kn-IN", "en-US"]
          }
        ]
      },
      {
        "name": "OpenAI",
        "provider": {
          "providerId": "openai",
          "label": "Open AI",
          "functionCalling": true,
          "multilingual": true
        },
        "models": [
          {
            "modelId": "gpt-4.1-mini",
            "label": "GPT-4.1-MINI",
            "functionCalling": true,
            "supportedLanguages": ["en-IN", "hi-IN", "en-US"]
          },
          {
            "modelId": "gpt-4o-mini",
            "label": "GPT-4o Mini",
            "functionCalling": true,
            "supportedLanguages": ["en-IN", "hi-IN", "en-US"]
          }
        ]
      }
    ]
  }
}
```

## Response Fields

| Field | Type | Description |
| - | - | - |
| `LLM[].name` | string | Human-readable provider display name. |
| `LLM[].provider.providerId` | string | Provider identifier. Use this as the `provider` value in `llmParams` when updating an agent. |
| `LLM[].provider.label` | string | Human-readable provider label. |
| `LLM[].provider.functionCalling` | boolean | Whether this provider supports function calling. |
| `LLM[].provider.multilingual` | boolean | Whether this provider supports multilingual agents. |
| `LLM[].models[].modelId` | string | Unique model identifier. Use this as the `model` value in `llmParams`. |
| `LLM[].models[].label` | string | Human-readable model display name. |
| `LLM[].models[].functionCalling` | boolean | Whether this specific model supports function calling. |
| `LLM[].models[].supportedLanguages` | string\[] | BCP-47 language codes supported by this model. |

## Errors

**401 Unauthorized** - Invalid or missing API key

```json theme={null}
{
  "status": "failure",
  "requestId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Invalid API key"
}
```

An unknown `provider` filter value returns HTTP `200` with an empty `LLM` array — not an error. See [Error Reference](https://docs.gnani.ai/Platform/Error_Reference.md) for other status codes.

## Use Cases

* Populating an LLM provider and model selector during agent creation or configuration
* Allowing users to switch between language models (e.g. from a smaller model to a larger one)
* Filtering models by provider when your organization has a specific LLM contract

> [!NOTE]
>
> The `provider.providerId` and `modelId` values returned here map directly to the `provider` and `model` fields in the **Update Agent** `llmParams` object. Use them as-is.

> [!TIP]
>
> Use the `provider` filter to show only the models available from your preferred LLM vendor, simplifying the selection UI for your users.

> [!NOTE]
>
> Save the `requestId` from every response. You will need it if you contact Gnani support to trace a specific request.


## OpenAPI

````yaml GET /v1/agents/config/llm_models
openapi: 3.0.3
info:
  title: Platform Agent Config API
  description: >-
    Read-only endpoints for discovering valid configuration values — languages,
    regions, timezones, LLM models, ASR providers, and TTS voices — before
    creating or updating agents.
  version: 2.1.0
servers:
  - url: https://api.inya.ai/platform
    description: Production server
security:
  - ApiKeyAuth: []
tags:
  - name: AgentConfiguration
    description: Agent configuration discovery operations
paths:
  /v1/agents/config/llm_models:
    get:
      tags:
        - AgentConfiguration
      summary: Get LLM models
      description: Retrieve all available LLM providers and their models.
      operationId: getLlmModels
      parameters:
        - name: provider
          in: query
          description: Filter results to a specific LLM provider
          required: false
          schema:
            type: string
            example: gnani
      responses:
        '200':
          description: Models retrieved successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StandardResponse'
              examples:
                success:
                  value:
                    status: success
                    requestId: a1b2c3d4-e5f6-7890-abcd-ef1234567890
                    message: Models retrieved successfully
                    response:
                      LLM:
                        - name: Gnani
                          provider:
                            providerId: gnani
                            label: Gnani
                            functionCalling: true
                            multilingual: true
                          models:
                            - modelId: Pampa Go
                              label: Pampa Go
                              functionCalling: true
                              supportedLanguages:
                                - en-IN
                                - hi-IN
                                - ta-IN
                                - kn-IN
                                - en-US
                        - name: OpenAI
                          provider:
                            providerId: openai
                            label: Open AI
                            functionCalling: true
                            multilingual: true
                          models:
                            - modelId: gpt-4.1-mini
                              label: GPT-4.1-MINI
                              functionCalling: true
                              supportedLanguages:
                                - en-IN
                                - hi-IN
                                - en-US
                            - modelId: gpt-4o-mini
                              label: GPT-4o Mini
                              functionCalling: true
                              supportedLanguages:
                                - en-IN
                                - hi-IN
                                - en-US
        '500':
          $ref: '#/components/responses/ServerError'
components:
  schemas:
    StandardResponse:
      type: object
      properties:
        status:
          type: string
          example: success
        requestId:
          type: string
          example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
        message:
          type: string
        response:
          type: object
    ErrorResponse:
      type: object
      properties:
        status:
          type: string
          example: failure
        requestId:
          type: string
          example: a1b2c3d4-e5f6-7890-abcd-ef1234567890
        message:
          type: string
  responses:
    ServerError:
      description: Internal server error
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: x-api-key
      description: API key with 'agents' permission

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.