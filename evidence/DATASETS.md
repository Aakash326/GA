# Dataset sources and provenance

The evaluation is a local convenience sample, not an official benchmark leaderboard or a population accuracy estimate.

| Source | Use | Attribution / terms |
|---|---|---|
| [Google SVQ](https://huggingface.co/datasets/google/svq) | Indian-language recognition, real acoustic environments and finance-related read questions | Google and contributors; CC-BY-4.0; utterance IDs and revisions retained |
| [Google FLEURS](https://huggingface.co/datasets/google/fleurs) | Longer read utterances | Google and contributors; CC-BY-4.0 |
| [MUSAN / OpenSLR 17](https://www.openslr.org/17/) | Controlled noise mixtures and non-speech inputs | David Snyder, Guoguo Chen and Daniel Povey; corpus CC-BY-4.0; the used free-sound subset carries a public-domain notice retained in `data/licenses/` |
| [MUCS 2021 / OpenSLR 104](https://www.openslr.org/104/) | Technical Hindi-English code-switching test utterances | Upstream CC-BY-SA-4.0 retained for extracted audio; conversion source and terms recorded in `data/next/dataset_replacement/ATTRIBUTION_AND_LICENSES.md` |
| Private team-call recordings | Excluded from the submitted benchmark | Raw audio, private text and call sessions are excluded from the ZIP. Only public dataset inputs contribute to reported recognition scores. |
| Authored TTS prompts and generated controls | Signs, numbers, IDs, times, negation, acronyms, length, silence and mitigations | Fictional values; target definitions and accepted/rejected readings retained |

Manifests record file paths, source IDs, speaker/source groups, reference status and audio hashes. Noise/codec derivatives retain their source relationship and are not independent speakers. The submission benchmark uses original dataset transcripts and explicit human TTS judgments. Reference revisions and exploratory assessments remain tagged separately and do not replace the submitted reference/scoring policy.

The 24-clip public extension contains 12 finance-related questions and 12 technical Hindi-English tutorial utterances. It does not represent banking transactions, all conversational code-switching patterns or a live telephone network. Selection is frozen in `data/next/dataset_replacement/selection.json`.

## Attribution and redistribution check — 15 November 2026

Upstream dataset cards specify [SVQ CC-BY-4.0](https://huggingface.co/datasets/google/svq/blob/main/README.md) and [FLEURS CC-BY-4.0](https://huggingface.co/datasets/google/fleurs/blob/main/README.md). Credit Google and the dataset contributors. Their audio is selected by source utterance IDs; source text is retained separately from adjudicated references. Changes include selection, PCM decoding/resampling and, where recorded in derivation metadata, noise mixing, pause insertion or telephone-codec simulation.

[MUSAN's upstream page](https://www.openslr.org/17/) specifies corpus CC-BY-4.0. The two used free-sound noise recordings are **noise-free-sound-0110** and **noise-free-sound-0055**. The mirror's [subset license](https://huggingface.co/datasets/FluidInference/musan/blob/main/noise/free-sound/LICENSE) and [annotations](https://huggingface.co/datasets/FluidInference/musan/blob/main/noise/free-sound/ANNOTATIONS) were retained as `data/licenses/MUSAN_free_sound_LICENSE.txt` and `MUSAN_free_sound_ANNOTATIONS.txt`; the notice identifies the selected recordings as public domain. These are source notices, not an independent authorship investigation.

[OpenSLR 104](https://www.openslr.org/104/) specifies **CC-BY-SA-4.0** for MUCS. That upstream license is preserved despite a different label on the conversion mirror. Credit MUCS 2021 / OpenSLR contributors and the linked conversion provider; selection/mono-PCM normalization is documented in `data/next/dataset_replacement/ATTRIBUTION_AND_LICENSES.md`. The extracted audio remains under the upstream share-alike terms. License texts: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) and [CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/).

Generated TTS and authored prompts are retained as evaluation artifacts, not relicensed public dataset assets. Fictional numeric/account/code targets are test stimuli, not customer identifiers. Personal/internal-call content is excluded from the distributable evidence. No broad rights claim is made for omitted private assets.

## Report 4 held-out banking extension

Exactly 15 new unused English banking-intent recordings are drawn from [PolyAI/MInDS-14](https://huggingface.co/datasets/PolyAI/minds14), licensed CC-BY-4.0 per its dataset card. The original dataset transcriptions, frozen source revision, source paths, audio hashes and target terms are in data/report4/asr_heldout_manifest.csv and asr_source_notice.json. The existing SVQ inventory did not supply enough unused clean financial-term recordings under the already frozen vocabulary, which was not changed. Source locale is en-US; API language hint is en-IN; speaker identity is unavailable. Audio/reference hashes do not overlap the existing benchmark. These 15 paired recordings remain a separate convenience cohort and do not change baseline WER. Prepared TTS prompts are newly authored synthetic test text, with frozen rules and hashes; human score sheets remain blank.

Coverage note: all 15 frozen target occurrences in the MInDS-14 sample are the word “account”. No bank-name or acronym gains can be inferred. All source WAVs are 8 kHz, preserved without resampling; source accent/channel differ from the original benchmark.
