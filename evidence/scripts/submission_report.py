"""Two-page reports for the public-audio/source-reference, human-TTS profile."""
import json,os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import SimpleDocTemplate,Spacer,PageBreak
from build_report import PROJECT,pct
from complete_report import para,table,footer,BODY,TITLE,SUB,HEAD,SMALL


def summary():
    p=Path(os.environ.get('GNANI_EVALUATION_SUMMARY',str(PROJECT/'results/submission/summary.json')))
    s=json.loads(p.read_text(encoding='utf8'))
    if s.get('profile')!='public_submission':raise ValueError('Reports require the public submission profile')
    return s


def saved(name):return json.loads((PROJECT/name).read_text(encoding='utf8'))


def document(name,title):
    registerFontFamily('DV',normal='DV',bold='DVB',italic='DV',boldItalic='DVB')
    return SimpleDocTemplate(str(PROJECT/name),pagesize=A4,leftMargin=13*mm,rightMargin=13*mm,topMargin=12*mm,bottomMargin=16*mm,title=title,author='Speech evaluation assignment')


def finish(doc,story,name):
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    from pypdf import PdfReader
    pages=len(PdfReader(str(PROJECT/name)).pages)
    if pages!=2:raise RuntimeError(f'{name}: expected two pages, got {pages}')
    print(f'{name}: 2 pages; public ASR, human TTS scores and separate provisional audio-model follow-up')


LANGS=[('en-IN','English'),('hi-IN','Hindi'),('te-IN','Telugu'),('ta-IN','Tamil'),('kn-IN','Kannada'),('mr-IN','Marathi')]


def build():
    s=summary();a=s['asr'];b=a['baseline'];n=a['followup'];pub=a['public24'];q=s['naturalness'];qc=s['tts_audio_quality']
    human={r['cohort']:r for r in s['tts_human']};v=s['playback_validation'];paired=s['paired_experiments']
    latency=s['latency'];diagnostics=s['request_diagnostics'];reliability=diagnostics['baseline_reliability']
    fresh=s.get('timbre_followup')
    fresh_latency={(r['model'],r['length']):r['median_ms']/1000 for r in fresh['rest_latency']} if fresh else {}
    fresh_means={r['model']:r for r in fresh['rating_summary'] if r['scope']=='rest_three_prompts_three_repeats'} if fresh else {}
    r4=s.get('report4');held=s.get('report4_heldout')
    controlled={(r['model'],r['length']):r for r in r4['controlled_rest']} if r4 else {}
    if r4:fresh_latency={key:r['request_total_ms_median']/1000 for key,r in controlled.items()}
    def series(model,field,places):return '/'.join(f'{controlled[model,length][field]:.{places}f}' for length in ['short','medium','long'])
    warm={r['model']:r for r in r4['streaming']['warm_ws']} if r4 else {}
    W=A4[0]-26*mm
    story=[para('Gnani speech evaluation',TITLE),para('Prisma ASR + Timbre TTS | Public-dataset evaluation · Tests: 13–15 Nov 2026',SUB),
           para('<b>Decision.</b> Suitable for a guarded, non-transactional support pilot. Confirm amounts, IDs, names, actions and negation before transactions. Multilingual recognition errors, critical TTS readings and v3.0 streaming gaps require mitigation.'),
           para('1. Scope and scoring method',HEAD),
           para(f'ASR: <b>{b["selected_clips"]} public baseline clips</b> ({b["speech_clips"]} speech + five no-speech), '
                '<b>120 follow-up</b> and <b>24 public extension</b> clips (12 finance questions + 12 technical Hindi-English). Sources: SVQ, FLEURS, MUSAN and MUCS. '
                'Cohorts have no repeated audio/source utterances but share speakers; noise/codec derivatives are paired observations. '+('A separate 15-clip banking cohort tests frozen keyterms; its scores do not enter baseline WER.' if held else '')),
           para('ASR scores use original dataset transcripts, NFC/case/Unicode-digit normalization and custom Levenshtein alignment. Corpus WER/CER = total edits / total reference length; raw scores are retained. Empty-reference controls have undefined WER/CER and separate false-transcription checks. '
                +('Original 164 TTS clips support selected correctness results; 66 prior valid outputs support version/functionality/reliability checks. New controlled timing and prepared listening cohorts remain separate; content scores below use human marks only.' if r4 else 'TTS: original 164 clips (98 baseline + 66 targeted), plus 66 new valid clips from 73 cases / 74 HTTP attempts; content scores below use human marks only.' if fresh else 'TTS: 164 generated clips (98 baseline + 66 targeted); content scores below use human marks only.'),SMALL),
           para('2. Recognition results',HEAD)]
    rows=[['Language','Clips (n)','Baseline WER','CER, no spaces','Follow-up WER (n=20)']]
    for code,label in LANGS:
        r=b['by_language'][code];rows.append([label,r['speech_clips'],pct(r['wer']),pct(r['cer_no_spaces']),pct(n['by_language'][code]['wer'])])
    story += [table(rows,[29*mm,29*mm,31*mm,34*mm,W-123*mm]),Spacer(1,3),
              para(f'Baseline corpus WER <b>{pct(b["wer"])}</b>; raw WER <b>{pct(b["raw_wer"])}</b>. '
                   f'Follow-up WER <b>{pct(n["wer"])}</b>. Public extension WER <b>{pct(pub["wer"])}</b>: '
                   f'finance questions {pct(pub["by_category"]["finance_related_questions"]["wer"])}, technical Hindi-English {pct(pub["by_category"]["technical_hindi_english_codeswitch"]["wer"])}.'),
              para('Five no-speech controls are excluded from language WER. Hindi groups the first locale, including Hindi-English hints. Follow-up data differ in difficulty/source; the columns are not paired before/after model estimates. Dataset-reference errors can affect WER.',SMALL),
              para('3. TTS quality on scored samples',HEAD)]
    rows=[['Scored subset','Clips with marks','Correct / scored targets','Wrong / ambiguous']]
    for name,label in [('baseline','Baseline'),('next','Targeted follow-up')]:
        r=human[name];rows.append([label,r['human_scored_prompts'],f'<b>{r["correct_targets"]}/{r["human_scored_targets"]} ({pct(r["strict_accuracy"])})</b>',f'{r["wrong_targets"]} / {r["ambiguous_targets"]}'])
    story += [table(rows,[47*mm,29*mm,62*mm,W-138*mm]),Spacer(1,3),
              para('Percentages are target correctness within the selected scored clips; unscored prompts are excluded. One clip may have several targets; ambiguous items fail strict correctness without proving omission. The failure-enriched follow-up is not directly comparable as a population estimate. Detailed target IDs and overlapping review marks are in the repository.',SMALL),
              para(f'<b>Exploratory ratings:</b> {q["unique_clips"]} distinct clips by {q["listeners"]} listener; naturalness mean/median <b>{q["naturalness_mean"]:.2f}/5</b>, '
                   f'prosody mean/median <b>{q["prosody_mean"]:.2f}/5</b>. Not population MOS or broad-language validation; language qualification/reveal order are incomplete.'),
              para(f'<b>Audio diagnostics:</b> {qc["decoded_nonempty"]}/{qc["clips"]} clips decoded nonempty; {qc["clips_with_near_full_scale_samples"]} had near-full-scale samples and '
                   f'{qc["clips_with_internal_low_energy_over_500ms"]} had internal low-energy intervals >0.5 s (maximum {qc["max_internal_low_energy_s"]:.2f} s). '
                   f'All {qc["clips_with_placeholder_header_lengths"]} REST WAVs use placeholder length fields; duration comes from decoded PCM. Level/pause flags are not perceptual failures.',SMALL),
              para('4. Observed failures',HEAD),
              table([['Evidence','Failure and practical consequence'],
                     ['ASR values / names','NUM-EN-01: <b>1499 → 1999</b>; DS-FIN-EN-01 dataset name <b>Gjakova → Chekov</b>. Plausible text can change a value or entity; confirm critical slots.'],
                     ['ASR acoustics / scripts',f'0 dB noise added <b>+{paired["acoustic_conditions"]["noise 0 dB SNR vs clean"]["delta_wer_pp"]:.1f} pp WER</b> on matched pairs. Word joining, rare names and cross-script substitutions recur.'],
                     ['TTS signs / IDs / times','Human marks: <b>T34/T40</b> negative values failed; <b>T52</b> 0070 read as seventy; <b>T44</b> 9:05 read as “nine five.” Fluent audio can still change meaning.'],
                     ['Empty audio / ambiguity',(f'Prior follow-up: <b>six v3.0 HTTP-200 empty WAVs</b>, plus one new listening-set failure. One prior HTTP 500 recovered. Validate positive PCM samples; valid audio with placeholder length fields is a separate issue. T21/NT066 remain ambiguous.' if r4 else f'Fresh: <b>{len(fresh["unexpected_failures"])} v3.0 HTTP-200 outputs were header-only WAVs</b>, including two rechecks; 48 kHz did not consistently fix them. One HTTP 500 recovered on retry. Reject empty PCM before playback. T21/NT066 remain ambiguous.' if fresh else f'T21/NT066 remain ambiguous. Logged failed REST TTS attempts: {reliability["tts"]["failed_attempts"]}/{reliability["tts"]["attempts"]}.')]],
                    [43*mm,W-43*mm]),
              PageBreak(),para('Playback, performance and improvements',TITLE),
              para('Measured behavior is separated from proposals requiring new validation.',SUB),para('5. Playback stall benchmark and latency',HEAD)]
    streams=latency['connections'];sec=lambda key:streams[key]['smooth_total_ms']/1000
    capacity={(r['kind'],r['requested_parallelism']):r for r in diagnostics['concurrency']}
    story += [table([['Test','Result and interpretation'],
                     ['ASR REST / streaming',f'Public baseline REST median <b>{b["latency_ms_median"]:.0f} ms</b>. Streaming: 18/18 completed; '
                      f'source-reference WER {pct(paired["ws"]["before"]["wer"])} REST vs {pct(paired["ws"]["after"]["wer"])} streaming; final transcript median {latency["asr_final_after_audio_ms_median"]:.0f} ms after clip end.'],
                     ['TTS non-streaming REST',((f'Controlled: <b>30 measured runs = 2 models × 3 texts × 5 repeats</b>; one text per length (61/396/930 characters), two warm-ups excluded. Seeded order; one request at a time. ' if r4 else 'Fresh three repeats per model/length: ')+f'Short/medium/long medians <b>v3.0 {fresh_latency["timbre-v3.0","short"]:.2f}/{fresh_latency["timbre-v3.0","medium"]:.2f}/{fresh_latency["timbre-v3.0","long"]:.2f} s</b>; '
                      f'<b>v2.5 {fresh_latency["timbre-v2.5","short"]:.2f}/{fresh_latency["timbre-v2.5","medium"]:.2f}/{fresh_latency["timbre-v2.5","long"]:.2f} s</b>. Full-body waits; voices differ. The separate earlier {fresh["rest_valid_clips"]}-file waveform set (18 earlier timing + 42 functionality files) is not pooled here; its early-gap detector found no flags.' if fresh else f'98 REST prompts: median {latency["tts_rest_latency_ms_median"]/1000:.2f} s; RTF {latency["tts_rest_rtf_median"]:.2f}.')],
                     *([['Audio duration / client RTF',f'Median duration, short/medium/long: v3.0 <b>{series("timbre-v3.0","duration_s_median",2)} s</b>; v2.5 <b>{series("timbre-v2.5","duration_s_median",2)} s</b>. Median per-trial RTF: v3.0 <b>{series("timbre-v3.0","rtf_client_median",3)}</b>; v2.5 <b>{series("timbre-v2.5","rtf_client_median",3)}</b>. Longer audio alone does not explain the observed response-time difference.']] if r4 else []),
                     ['Streaming / warm start',(f'Separate short-prompt warm WebSocket TTFA: <b>{warm["timbre-v3.0"]["ttfa_ms_median"]:.0f} ms v3.0 vs {warm["timbre-v2.5"]["ttfa_ms_median"]:.0f} ms v2.5</b> (five each, cold warm-ups excluded). Immediate playout underruns: <b>5/5 vs 0/5</b>. Earlier N8: 12/12 vs 0/2; fresh SSE: 3/3 vs 0/3. These are distinct saved-trace cohorts, not handset tests.' if r4 else f'Client-side playout: <b>{v["v3_with_stalls"]}/{v["v3_streams"]} tested v3.0 streams</b> underrun after first audio; '
                      f'retrospective extra wait <b>{v["v3_extra_wait_ms_min"]/1000:.3f}–{v["v3_extra_wait_ms_max"]/1000:.3f} s</b>. '
                      f'v2.5 controls: <b>{v["v25_with_stalls"]}/{v["v25_streams"]}</b>. '+('Fresh short/medium/long streams: <b>3/3 v3.0 underrun; 0/3 v2.5</b>. ' if fresh else '')+'Small tested configurations do not establish general model superiority.')],
                     ['Independent buffer replay',('32 traces (14 earlier SSE + 6 later SSE + 10 warm WS + 2 cold WS warm-ups); <b>576 replay conditions</b>: 0/50/100/200/500/1000 ms buffers × 1/10/20 ms tolerances. At 1000 ms, v3.0 still underruns in <b>2/3 fresh SSE</b> and <b>3/5 warm WS</b>; v2.5 controls remain continuous. The buffer adds startup delay; future-aware gap-free starts are separate bounds.' if r4 else f'<b>{v["byte_duration_checks_passed"]}/{v["streams"]}</b> chunk byte totals match decoded PCM audio. Integer-sample reconstruction confirms the stall counts. Sensitivity: 0/50/100/200 ms prebuffers and 1/10/20 ms tolerances retain the tested 12/12 vs 0/2 finding. Retrospective gap-free replay uses future arrivals.')],
                     ['Concurrency / short soak',f'At eight parallel requests, TTS completed <b>{capacity["tts",8]["successful_requests"]}/8</b> after retries; ASR <b>{capacity["asr",8]["successful_requests"]}/8</b> with {capacity["asr",8]["retried_requests"]} retried. '
                      f'Low-rate ten-minute soak: {diagnostics["soak"]["successes"]}/{diagnostics["soak"]["requests"]} completed. Request concurrency is not concurrent-call capacity.']],
                    [45*mm,W-45*mm]),
              para('REST timers span dispatch → full response body; RTF uses decoded PCM duration. First audio is the first playable chunk. Underruns exceed the selected lateness tolerance; 1 ms is the original definition. Cold timings include handshake; retry-inclusive timing includes backoff. Results apply to this client/account/request mix; region was not logged.',SMALL),
              para('6. Prioritized recommendations',HEAD),
              table([['Priority','Evidence and recommended change'],
                     ['P0 · Protect critical meaning','Read back amounts, signs, IDs, names, actions and negation before transactions. Preserve zeros, digit order and negation scope in slot checks. Validate on unseen transaction utterances.'],
                     ['P0 · Rewrite risky TTS text','Write “minus”, expand times and separate identifier digits. Among <b>nine complete human-reviewed pairs</b>, eight changed from failing raw to correct rewritten, and one failed both. This selected sample does not establish general gain. Decode/remux WAVs before relying on header lengths.'],
                     ['P1 · Stream and queue safely','V2.5 was more promising in the tested playback configurations; larger paired and real-handset tests are required before a deployment choice. Reuse connections and queue requests under the account limit; validate online buffering and interruption cleanup.'],
                     ['P1 · Validate expression and pacing',('V3.0 tags were exercised; <b>superior perceived quality was not established</b>. Earlier automated ratings (3.22/5 naturalness, 3.11/5 prosody for both on nine clips each) are exploratory and missed a planted gap. New study: 15 matched neutral pairs plus tagged/control material; three-listener sheet and ten held-out rewrite pairs await human marks.' if r4 else f'Gnani documents 13 v3.0 tags; v2.5 strips them. Tested all 13 in English plus four Hindi variants. Speed 0.85/1.15 changed duration in the expected direction for both models. '
                      f'Audio-model screen: {fresh["blind_judgments"]} clips; repeated neutral-prompt naturalness/prosody means '
                      f'v3.0 {fresh_means["timbre-v3.0"]["naturalness_mean"]:.2f}/{fresh_means["timbre-v3.0"]["prosody_mean"]:.2f}, '
                      f'v2.5 {fresh_means["timbre-v2.5"]["naturalness_mean"]:.2f}/{fresh_means["timbre-v2.5"]["prosody_mean"]:.2f} /5 (nine clips each). Provisional, not human MOS; the judge missed a planted gap.' if fresh else 'Freeze ASR keyterms before held-out testing; validate expression and pacing with qualified listeners.')],
                     ['P2 · Validate hints independently',('Frozen vocabulary, 15 new 8 kHz banking clips: <b>WER 19.33% → 18.67%</b>; one improved, 14 unchanged, none regressed. Target word “account”: <b>14/15 → 15/15</b>; no hinted-token insertion flags. US-English, unknown speakers and one-term coverage limit generalization; bank-name/acronym gains remain untested.' if held else 'Use independent language-qualified listeners and freeze ASR vocabulary before held-out paired testing.')]],
                    [45*mm,W-45*mm]),
              para('7. Reproducibility and decision limits',HEAD),
              para('<b>Run:</b> <font name="DVB">python run_evaluation.py --mode replay --part all --reports</font>. '
                   'The submission profile rebuilds source-reference ASR, human TTS scores and the separately labeled cached audio-model screen, with hashes and custom metric tests. '
                   'See <font name="DVB">REPORT4_IMPLEMENTATION.md</font> and <font name="DVB">TIMBRE_FOLLOWUP.md</font> for versioned tables and audio. Replay needs no new API calls.',SMALL),
              para('The cause of v3.0 REST delay remains unresolved: client RTF/TTFA cannot isolate compute, queueing or network stages without provider traces. These convenience samples have source-reference and voice-mismatch limitations. '
                   'Real handset/Exotel validation, transaction safety, extended load and generalized mitigation benefits remain unvalidated. Proceed only with a guarded support pilot and confirmation of critical outputs.',SMALL)]
    finish(document('report.pdf','Gnani speech evaluation — public dataset and human listening'),story,'report.pdf')


def build_supplement():
    import csv
    s=summary();W=A4[0]-26*mm;h={r['cohort']:r for r in s['tts_human']};fresh=s.get('timbre_followup')
    def rows(name):
        with (PROJECT/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
    quality=rows(Path(os.environ.get('GNANI_EVALUATION_SUMMARY',str(PROJECT/'results/submission/summary.json'))).parent/'tts_human_quality_ratings.csv')
    validation=rows('results/playback_validation/playback_validation.csv')
    sensitivity=s['playback_validation']['buffer_sensitivity']['aggregation']
    def count(buffer,tolerance,model):
        r=next(r for r in sensitivity if r['initial_prebuffer_ms']==buffer and r['tolerance_ms']==tolerance and r['model']==model)
        return f'{r["streams_with_underflows"]}/{r["streams"]}'
    story=[para('Supplementary evaluation evidence',TITLE),para('Original dataset references · Human listening · Reproducible playback benchmark',SUB),
           para('1. Public ASR scope and source-reference results',HEAD),
           table([['Cohort','Speech / controls','Word edits / ref words','WER / raw WER'],
                  *[[name,f'{r["speech_clips"]} / {r["no_speech_controls"]}',f'{r["word_edits"]} / {r["reference_words"]}',f'{pct(r["wer"])} / {pct(r["raw_wer"])}'] for name,r in s['asr'].items()]],
                 [38*mm,38*mm,52*mm,W-128*mm]),Spacer(1,4),
           para('Only public audio contributes to this benchmark. Original dataset transcripts are frozen and used consistently across cohorts. '
                'Corpus WER sums edits and reference words. Empty controls are excluded from speech WER; original/normalized text and S/D/I are exported.'),
           para('Cohorts have no duplicate audio or source utterances. They share speakers, and derived noise/codec clips retain parent IDs. Baseline language grouping uses the first locale; follow-up results are non-paired samples. The 24-clip extension is exactly the 12 finance questions and 12 technical Hindi-English utterances, not another copy of those cohorts.',SMALL),
           para('2. Human TTS content and perceptual ratings',HEAD),
           table([['Cohort','Human-scored clips','Correct / targets','Wrong / ambiguous','Critical correct / targets'],
                  *[[name,r['human_scored_prompts'],f'{r["correct_targets"]}/{r["human_scored_targets"]}',f'{r["wrong_targets"]}/{r["ambiguous_targets"]}',f'{r["critical_correct"]}/{r["critical_targets"]}'] for name,r in h.items()]],
                 [31*mm,36*mm,37*mm,35*mm,W-139*mm]),Spacer(1,4),
           para('The 110 reported targets across 66 clips have explicit human marks. Unmarked targets do not enter these scores. The sample is deliberately enriched for suspected failures; neither target correctness nor the raw/rewrite gains estimate general population accuracy. Ambiguity fails strict correctness without proving an omission.'),
           table([['Clip','Listener','Naturalness / 5','Prosody / 5','Repeated target rows'],
                  *[[r['case_id'],r['listener_id'],r['naturalness_1to5'],r['prosody_1to5'],r['repeated_target_rows']] for r in quality]],
                 [28*mm,27*mm,43*mm,40*mm,W-138*mm]),Spacer(1,4),
           para('<b>Exploratory perceptual ratings:</b> four unique clips, one listener. Naturalness mean/median 4.50/5; prosody mean/median 5.00/5. '
                'The seven target rows are repeated clip-level ratings, not seven independent observations. Reveal order/language qualifications are incomplete; this is a descriptive check, not population MOS.'),
           para('The prepared 12-clip study adds a common 1–5 rubric, intelligibility and critical-term checks. Its blank response sheet is not treated as collected evidence. '
                'Objective audio diagnostics separately check all 164 files for decode integrity, near-full-scale samples and low-energy intervals; silence may be intentional.',SMALL),
           PageBreak(),para('Playback benchmark verification',TITLE),para('Saved network timing reconstructed into actual PCM playback WAVs',SUB),
           para('3. Independent verification of the v3.0 pause',HEAD),
           table([['Model / language','Rate','Tested / underrun','Extra-wait range'],
                  *[[model.replace('timbre-','')+' / '+language,rate,f'{len(g)} / {sum(int(r["immediate_stalls"])>0 for r in g)}',f'{min(float(r["extra_wait_ms"]) for r in g)/1000:.3f}–{max(float(r["extra_wait_ms"]) for r in g)/1000:.3f} s']
                    for model in ['timbre-v3.0','timbre-v2.5'] for language in ['en-IN','hi-IN'] for rate in ['24000','8000']
                    if (g:=[r for r in validation if r['model']==model and language in r['case_id'] and r['sample_rate_hz']==rate])]],
                 [61*mm,25*mm,47*mm,W-133*mm]),Spacer(1,4),
           para('All 14 chunk-byte totals match the saved mono PCM16 WAV frame counts. A separate integer-sample scheduler reconstructs when audio would play, inserting zeros only during buffer underruns. '
                '<b>All 12 tested v3.0 streams underrun; both tested v2.5 controls remain continuous.</b> These small, configuration-specific cases do not establish v2.5 superiority or live-handset reliability. Retrospective delayed replay uses future arrivals and is not an online buffering policy.'),
           table([['Initial prebuffer','v3.0: 1 ms tolerance','10 ms','20 ms','v2.5: all tolerances'],
                  *[[f'{buffer} ms',count(buffer,1,'timbre-v3.0'),count(buffer,10,'timbre-v3.0'),count(buffer,20,'timbre-v3.0'),count(buffer,1,'timbre-v2.5')] for buffer in [0,50,100,200]]],
                 [33*mm,50*mm,23*mm,23*mm,W-129*mm]),Spacer(1,4),
           para('All 168 stream/buffer/tolerance conditions preserve decoded PCM and arrival timestamps. Per-stream exports record underrun count, total starvation, startup delay and time after the final underrun. Stability is retrospective, not an online detector. Larger paired/configuration-balanced controls are required before production selection.',SMALL),
           para('The earlier rounded chunk durations produce at most 1.18 ms difference from exact sample arithmetic. Exact v3.0 extra wait is 0.845–3.911 s. '
                'There are 28 playback WAVs: immediate and retrospectively delayed for every trace. Open results/playback_validation/index.html to compare them. '
                'Initial zeros represent measured startup; later zeros represent network underruns. This is offline reconstruction, not a new device or live-network test.'),
           para('4. Measurement boundaries and next checks',HEAD),
           para('First audio is the first decoded playable chunk from synthesis dispatch. Cold timings include handshake; warm WebSocket timings use an established connection. '
                'REST latency ends at full-body receipt; RTF divides by decoded duration. A stall exceeds a 1 ms scheduling tolerance. Retry-inclusive duration includes REST backoff (maximum four attempts; 1, 2, 4 s waits).'),
           para('Account tests completed 2/8 parallel TTS requests after retries and 8/8 ASR with six retried; the short soak completed 30/30 requests. '
                'This is not eight-call capacity or long-load reliability. Collection: 13–15 Nov 2026; region was not recorded.',SMALL)]
    if fresh:
        story += [para('5. Fresh Timbre 3.0 / 2.5 follow-up',HEAD),
                  para(f'{fresh["attempted_cases"]} cases / {fresh["http_requests"]} HTTP attempts: {fresh["valid_audio_clips"]} valid clips, {len(fresh["unexpected_failures"])} header-only WAV failures, one recovered HTTP 500 and one expected tag-only HTTP 400. '
                       'Three repeated REST lengths still show upfront v3.0 delay. Fresh SSE: 3/3 v3.0 streams underrun; 0/3 v2.5 controls. Completed REST files have no early sound–gap energy flags. '
                       f'All 13 documented v3.0 tags, Hindi variants, v2.5 stripping controls, speed, 24/48 kHz and raw/spoken numeric text were exercised. '
                       f'{fresh["blind_judgments"]} blind audio-model ratings and {fresh["paired_judgments"]} condition-order-hidden comparisons remain provisional. The judge missed a planted 900 ms gap, so it cannot certify pause timing. '
                       'Per-tag results, failures and replay instructions: TIMBRE_FOLLOWUP.md; playable clips: results/timbre_followup/index.html.',SMALL)]
    if s.get('report4'):
        r4=s['report4'];held=s['report4_heldout'];idx=next(i for i,p in enumerate(story) if isinstance(p,PageBreak))
        story=story[:idx]+[PageBreak(),para('Controlled timing and outcome audit',TITLE),para('Report-4 extension · Saved trials, positive PCM checks and fixed-buffer replay',SUB),
             para('3. Five-repeat matched-input REST comparison',HEAD),
             table([['Version / length','Valid / attempts','REST median (range), s','Audio median, s','Client RTF median'],
                    *[[r['model'].replace('timbre-','')+' / '+r['length'],f'{r["successful_trials"]}/{r["attempts"]}',
                       f'{r["request_total_ms_median"]/1000:.3f} ({r["request_total_ms_min"]/1000:.3f}–{r["request_total_ms_max"]/1000:.3f})',
                       f'{r["duration_s_median"]:.2f}',f'{r["rtf_client_median"]:.3f}'] for r in r4['controlled_rest']]],
                   [34*mm,27*mm,58*mm,33*mm,W-152*mm]),Spacer(1,4),
             para('Inputs: identical 61/396/930-character English strings, speed 1.0, mono PCM16 at 24 kHz, same client/endpoint. 30 measured requests = 2 models × 3 texts × 5 repeats; one text per length. Two REST warm-ups are excluded. The earlier 60-file waveform set = 18 earlier timing + 42 functionality outputs, with no shared case IDs; it is not pooled into these medians. Seeded order; no overlapping synthesis. Tarika/Kaveri are different voices. Full-response latency is not TTFA. RTF divides each request time by its own decoded audio duration before aggregation. No p95 is reported at n=5. Cause remains unresolved without provider stage traces.',SMALL),
             para('4. Disjoint HTTP attempts and eventual outcomes',HEAD),
             table([['HTTP cohort','Cases / attempts','Valid / empty / HTTP errors','Attempt success','Eventual case success'],
                    *[[name.replace('timbre_followup','Prior follow-up').replace('report4_controlled','Controlled REST').replace('report4_quality','Listening / rewrites'),
                       f'{r["cases"]}/{r["http_attempts"]}',f'{r["valid_pcm_attempts"]}/{r["disjoint_attempt_outcomes"].get("empty_pcm",0)}/{r["disjoint_attempt_outcomes"].get("http_error",0)}',
                       pct(r['attempt_success_rate']),pct(r['eventual_case_success_rate'])] for name,r in r4['http_cohorts'].items()]],
                   [39*mm,27*mm,48*mm,33*mm,W-147*mm]),Spacer(1,4),
             para('Prior follow-up: 74 attempts include six HTTP SSE requests, one recovered HTTP 500 and one intentionally invalid tag-only HTTP 400. Eight separate rechecks retain their original failed cases. Positive-case success excludes the expected rejection: 66/72. These diagnostic rates are not production reliability estimates. Empty PCM fails even at HTTP 200; placeholder WAV lengths with positive PCM are separate. SSE wire-body byte counts were not saved and are marked unavailable.',SMALL),
             para('5. Warm first-audio timing and buffering tradeoff',HEAD),
             para('Separate short-prompt WebSocket trials: five warm successes per model; TTFA medians 813 ms (v3.0, range 267.5–3015.5) and 161.3 ms (v2.5, 156.6–171.5). Two cold socket warm-ups are excluded. All five v3.0 immediate playouts underrun; none of five v2.5 controls do. No actual handset calls are represented.',SMALL),
             table([['Fixed startup buffer','Fresh SSE v3.0','Warm WS v3.0','V2.5 SSE / WS'],
                    *[[f'{b} ms',
                       str(next(r['streams_with_underflows'] for r in r4['streaming']['buffer_summary'] if r['cohort']=='fresh_SSE' and r['model']=='timbre-v3.0' and r['buffer_ms']==b))+'/3',
                       str(next(r['streams_with_underflows'] for r in r4['streaming']['buffer_summary'] if r['cohort']=='report4_WS' and r['phase']=='warm_measured' and r['model']=='timbre-v3.0' and r['buffer_ms']==b))+'/5',
                       '0/3; 0/5'] for b in [0,200,500,1000]]],[45*mm,44*mm,44*mm,W-133*mm]),Spacer(1,4),
             para('32 traces = 14 earlier SSE + 6 later SSE + 10 warm WS + 2 cold WS warm-ups (R4-WARM-WS-3-1 / R4-WARM-WS-25-1). Warm-ups are excluded from warm TTFA. All byte totals match PCM; 576 conditions cover six buffers and three tolerances. Larger buffers trade startup delay for fewer underruns. The future-aware gap-free bound remains separate from observed TTFA; no universal production threshold is chosen. CSV chunk/buffer logs, plots and six new playback examples are at results/report4/index.html.',SMALL),
             para('6. Held-out results and remaining human work',HEAD),
             para(f'Frozen keyterms on 15 unused public MInDS-14 banking clips: word edits 29/150 → 28/150; WER 19.33% → 18.67%; CER 15.83% → 15.25%. One improved, 14 unchanged, none regressed. Target word “account”: 14/15 → 15/15; no hinted-token insertion flags. These are 8 kHz US-English recordings with unknown speaker identities; bank-name/acronym benefit remains untested. Critical-slot exports are lexical checks, not full semantic verification.',SMALL),
             para(f'Prepared: {held["quality_audio_available"]}/{held["quality_audio_planned"]} quality outputs (15 matched neutral prompt pairs plus extra material), three-listener blinded sheet, and ten held-out raw/rewrite pairs on v2.5. One new v3.0 quality request returned empty audio. <b>No new human quality or rewrite marks are collected.</b> Open results/report4_quality/listening.html and rewrites.html; do not treat blank templates as results.',SMALL)]
    finish(document('next_stages_report.pdf','Supplementary speech and playback evaluation'),story,'next_stages_report.pdf')
