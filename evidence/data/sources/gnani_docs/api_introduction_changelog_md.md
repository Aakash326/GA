> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Changelog

> What changed in the Gnani Speech APIs, newest first.

Documentation changes for the Gnani Speech APIs, newest first. Dates are the dates the documentation changed, except Prisma v3.0, which uses its release date. For Python SDK releases, see [`gnani-vachana` on PyPI](https://pypi.org/project/gnani-vachana/). For the other sections, see [all changelogs](https://docs.gnani.ai/changelog).

<ul />

## Release notes

Detailed notes for releases that need action or migration guidance.

**22 October 2026**

Prisma v3.0

## Prisma v3.0 speech-to-text model

`prisma-v3.0` is a multilingual speech-to-text model for nine Indian languages and English. It can identify the spoken language by itself.

**Action required: none.** Prisma v3.0 is opt-in and Prisma v2.5 remains the default model, so existing integrations keep working. There are no breaking changes and no deprecations in this release.

### New models and capabilities

* **Prisma v3.0.** One model for `hi-IN`, `bn-IN`, `ta-IN`, `te-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `gu-IN`, `pa-IN` and `en-IN`. See [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md) and [Models](https://docs.gnani.ai/api/STT/models/overview.md).
* **Automatic language detection.** Send `language_code=indic-auto`, or send one to four language codes as a comma-separated list such as `hi-IN,en-IN`. They are hints, not a lock: the transcript follows the language actually spoken. Responses include `detected_language_code`.
* **Two more output styles**, next to `verbatim` and `transcribe`. `codemix` is available on REST, Batch and Realtime. `transliterate` writes the whole transcript in Latin letters and is available on REST and Realtime. See [Output styles](https://docs.gnani.ai/api/STT/models/prisma-v3.md#output-styles) and [Romanised output](https://docs.gnani.ai/api/STT/models/prisma-v3.md#romanised-output-transliterate).
* **Context hints.** `keyterms`, `topic`, `previous_text` and `speaker_names` can improve accuracy. On REST you can send any combination of the four. Realtime accepts `keyterms` only (`x-keyterms`).

### API changes

* **Choose the model.** REST: form field `model=prisma-v3.0` on [`POST /stt/v3`](https://docs.gnani.ai/api/STT/speech-to-text). Realtime: header `x-model: prisma-v3.0` on [`WS /stt/v3/stream`](https://docs.gnani.ai/api/STT/stt-websocket). Batch: `config.model` in [Create Job](https://docs.gnani.ai/api/STTBatch/Create_Job.md). See [Where you can use it](https://docs.gnani.ai/api/STT/models/prisma-v3.md#where-you-can-use-it).
* **Realtime.** `x-format` accepts `codemix` and `transliterate`. `lang_code` is optional with `transliterate`. `lang_code` accepts a comma-separated list of up to four languages. See [Prisma v3.0 on streaming](https://docs.gnani.ai/api/STT/stt-websocket.md#prisma-v3-0-on-streaming).
* **Batch.** With `prisma-v3.0` the model identifies the language of each segment, and `config` accepts `format`, `keyterms`, `topic` and `speaker_names`. See [Prisma v3.0 options](https://docs.gnani.ai/api/STTBatch/Introduction.md#prisma-v3-0-options).
* **New error types**, such as `INVALID_CONTEXT` and `MODEL_UNSUPPORTED_LANGUAGE`. See the [Error Reference](https://docs.gnani.ai/api/introduction/errors.md).
* **Missing `language_code` on REST** returns `422` with a `{"detail": [...]}` body instead of the usual error envelope. It is optional only with `format=transliterate`.

### Improvements

* New reference pages: [Models](https://docs.gnani.ai/api/STT/models/overview.md), [Prisma v2.5](https://docs.gnani.ai/api/STT/models/prisma-v2-5.md), [Error Reference](https://docs.gnani.ai/api/introduction/errors.md) and [Limits](https://docs.gnani.ai/api/STT/limits.md).
* Accepted values for TTS and Voice Cloning `audio_config`, and for Batch `bias_score` and the job `status` filter, are now shown as tables.
* On Realtime, `segment_index` starts at 1 and `segment_id` has the form `<request_id>-seg-<N>`.

### If you switch to Prisma v3.0

Some responses differ from Prisma v2.5. Check these before you switch:

* With a fixed `hi-IN` or `en-IN` and no `format`, REST returns digits (`transcribe`). Prisma v2.5 returned `verbatim`. Send `format` explicitly to keep your current output.
* The `model` value in responses is `prisma-v3.0`. Update any code that checks it.
* REST responses do not include `timestamp`. Use `request_id` instead.
* `itn_native_numerals` and `x-itn-native-numerals` have no effect, and `output.literal` is not returned on Realtime. The model writes numbers itself.

The full list is in [How it differs from Prisma v2.5](https://docs.gnani.ai/api/STT/models/prisma-v3.md#how-it-differs-from-prisma-v2-5).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.