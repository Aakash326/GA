"""Offline replay of the separately collected Timbre follow-up. Never calls an API."""
import csv,hashlib,html,json,statistics,sys,wave
from collections import Counter
from pathlib import Path

P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'scripts'))


def read(path):
    if not Path(path).exists():return []
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def write(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def yes(value):return value is True or str(value).lower()=='true'


def reconstruct(records,out):
    from validate_playback import schedule,render
    rows=[]
    for a in records.values():
        if a.get('kind')!='tts_stream' or not a.get('ok'):continue
        timeline=P/a['timeline_path'];chunks=json.loads(timeline.read_text())['chunks']
        with wave.open(str(P/a['audio_path']),'rb') as w:
            rate=w.getframerate();frames=w.getnframes();pcm=w.readframes(frames)
            if w.getnchannels()!=1 or w.getsampwidth()!=2:raise ValueError('Expected mono PCM16')
        lengths=[c['bytes']//2 for c in chunks]
        if any(c['bytes']%2 for c in chunks) or sum(lengths)!=frames:raise ValueError('Invalid chunk sample counts')
        arrivals=[round(c['t_s']*rate) for c in chunks];immediate=schedule(arrivals,lengths,rate)
        if len(immediate['gaps'])!=a['stalls']:raise ValueError('Playback count differs from saved trace')
        smooth=schedule(arrivals,lengths,rate,start=immediate['earliest_start'])
        for label,result in [('immediate',immediate),('delayed',smooth)]:
            path=out/'playback'/f'{a["case_id"]}__{label}.wav';path.parent.mkdir(exist_ok=True)
            render(path,pcm,lengths,result['starts'],rate)
        rows.append(dict(case_id=a['case_id'],model=a['settings']['model'],voice=a['settings']['voice'],
                         chunks=len(chunks),sample_rate_hz=rate,pcm_frames=frames,chunk_frames=sum(lengths),
                         timeline_sha256=digest(timeline),first_audio_ms=arrivals[0]/rate*1000,
                         underruns=len(immediate['gaps']),starvation_s=sum(n/rate for _,n in immediate['all_gaps']),
                         extra_wait_ms=(immediate['earliest_start']-arrivals[0])/rate*1000,
                         immediate_path=f'playback/{a["case_id"]}__immediate.wav',
                         delayed_path=f'playback/{a["case_id"]}__delayed.wav',
                         gaps=json.dumps([dict(start_s=p/rate,duration_s=n/rate) for p,n in immediate['gaps']])))
    write(out/'stream_playback.csv',rows);return rows


def tag_evidence(metrics,blind,pairs):
    rows=[]
    for m in metrics:
        if m['section'] not in ['tag','invalid_tag']:continue
        b=blind.get(m['case_id'],{});p=pairs.get(m['case_id'],{});side=p.get('condition_side','')
        literal=yes(b.get('tag_words_spoken')) or yes(p.get('literal_tag_spoken_'+side))
        preserved=yes(p.get('content_preserved_'+side)) if p else None
        if not p:status='not_assessed'
        elif literal:status='possible_literal_tag'
        elif m['expected_policy']=='render_tag':
            if p.get('more_cue')==side and yes(p.get('cue_audible_'+side)) and preserved:status='cue_demonstrated'
            elif p.get('more_cue')=='indistinguishable':status='not_distinguished'
            else:status='uncertain_or_control_preferred'
        else:status='no_literal_tag_detected' if preserved else 'content_uncertain'
        rows.append(dict(case_id=m['case_id'],model=m['model'],language=m['language'],tag=m['tag'],
                         documented_policy=m['expected_policy'],status=status,more_cue=p.get('more_cue'),condition_side=side,
                         condition_cue_preferred=p.get('more_cue')==side and yes(p.get('cue_audible_'+side)),
                         observed_delivery=b.get('observed_delivery'),nonverbal_events=b.get('nonverbal_events'),
                         literal_tag_flag=literal,condition_content_preserved=preserved,
                         neutral_duration_s=next((x['duration_s'] for x in metrics if x['case_id']==m['neutral_case_id']),None),
                         tagged_duration_s=m['duration_s'],longest_internal_low_energy_s=m['longest_internal_low_energy_s'],
                         blind_reason=b.get('reason'),pair_reason=p.get('reason'),assessor='audio_model_provisional'))
    return rows


def markdown_report(s,metrics,blind,tags):
    lines=['# Timbre 3.0 and 2.5 follow-up — 15 November 2026','',
           'This extension is separate from the original 164 TTS clips and human content scores. All new speech is synthesized from prepared prompts; no private or newly recorded speech is used.','',
           '## Gnani guidance checked','',
           '- [REST inference](https://docs.gnani.ai/api/TTS/tts-inference): use each model’s own voice catalog, set language explicitly, and choose speed within 0.85–1.15. REST returns complete audio; sending the full input text does not imply immediate playback.',
           '- [Audio tags](https://docs.gnani.ai/api/TTS/tts-audio-tags): 13 case-sensitive inline expression/nonverbal/pacing tags are documented for v3.0. v2.5 strips tags; tag-only input should return 400. Unknown tags should not be spoken.',
           '- [Normalization guide](https://docs.gnani.ai/api/TTS/tts-input-formating): describes automatic number/date/ID normalization. The REST introduction still warns about raw numbers, so numeric behavior was tested rather than assumed.',
           '- [Voices](https://docs.gnani.ai/api/TTS/available-voices) and [transport guidance](https://docs.gnani.ai/api/TTS/tts-websocket): Tarika/Shivani were used for v3.0, Kaveri/Nalini for v2.5; these are different voices. Gnani recommends realtime transport for interactive use and REST for complete files.',
           '- No published note confirming a fix for the previously observed startup gap was found in the checked documentation/changelog. These are public API instructions, not a claim of direct support correspondence.','',
           '## Experiment and outcomes','',
           f'{s["planned_cases"]} planned cases, {s["attempted_cases"]} attempted across {s["http_requests"]} HTTP attempts; {s["valid_audio_clips"]} valid audio clips, {len(s["unexpected_failures"])} HTTP-200 empty WAVs and {len(s["expected_rejections"])} expected tag-only rejection. One v3.0 speed-control request received HTTP 500 before a successful retry; the failed attempt is retained. The first batch had 65 cases; eight explicitly identified 24/48 kHz rechecks follow four initial header-only failures. These diagnostic counts are not population failure-rate estimates.','',
           'Latency uses three sequential repeats for each of three English prompts per model, at 24 kHz. Fixed alternating v3.0/v2.5 ordering; voice, server load, region and connection cold state were not controlled. There are three distinct prompt texts, not nine independent text samples. Tags, Hindi controls, invalid tags, speed extremes, 48 kHz and raw/spoken numeric inputs extend the matrix.','',
           '## Non-streaming latency and the sound–silence question','',
           '| Model / voice | Length / characters | Runs | Full-response median | Range | Median audio |',
           '|---|---|---:|---:|---:|---:|']
    for r in s['rest_latency']:
        lines.append(f'| {r["model"]} / {r["voice"]} | {r["length"]} / {r["text_characters"]} | {r["n"]} | {r["median_ms"]/1000:.3f} s | {r["min_ms"]/1000:.3f}–{r["max_ms"]/1000:.3f} s | {r["median_audio_s"]:.2f} s |')
    lines += ['',f'Yes, v3.0 still has a substantial wait with non-streaming REST in these tests. This interval ends at full-body receipt, before playback; it is not time to first playable audio. Among {s["rest_valid_clips"]} completed REST clips, the 10 ms RMS detector flagged {len(s["rest_early_gap_energy_flags"])} short initial bursts followed by at least 500 ms of quiet. Sensitivity uses −35/−45/−55 dBFS. This does not certify absence of every perceptual pause. Ordinary phrase pauses and requested `<pauses>` are separate from network underruns.', '',
              'All text was sent in one request for both REST and SSE. SSE streams the output audio. A completed REST file cannot experience missing network chunks during offline playback; a zero-sample response is a different failure.', '',
              '| Fresh SSE case | First audio | Underruns after start | Total starvation |', '|---|---:|---:|---:|']
    for r in s['fresh_streams']:lines.append(f'| {r["case_id"]} | {r["first_audio_ms"]/1000:.3f} s | {r["underruns"]} | {r["starvation_s"]:.3f} s |')
    lines += ['', 'All six trace byte totals match saved PCM frames. Actual chunks were placed at sample-accurate arrival positions; zero insertion renders network gaps. Future-aware delayed versions are diagnostic, not a deployable buffer guarantee. Fresh results are not pooled with the earlier 14-stream benchmark.', '',
              '## Expression, emotional delivery and prosody','',
              'The API documents expression cues such as excitement/whispering/shouting, nonverbal sounds and pacing; there is no tested generic emotion parameter. All 13 documented v3.0 tags were exercised in English and four in Hindi. Models/condition order were hidden for paired judgments; the requested cue is necessarily disclosed in the paired stage. An earlier blind stage receives audio alone, without intended text, model or cue.', '',
              '| Model | Language | Tag | Initial trial result | Provisional pair result |', '|---|---|---|---|---|']
    by_id={r['case_id']:r for r in tags}
    for row in read(P/'data/timbre_followup_cases.csv'):
        if row['section']!='tag':continue
        result=by_id.get(row['case_id'])
        lines.append(f'| {row["model"]} | {row["language"]} | `<{row["tag"]}>` | '+('valid audio' if result else 'header-only / no audio')+f' | {result["status"] if result else "not assessable"} |')
    lines += ['', '`cue_demonstrated` requires the pair judge to prefer the tagged clip for the intended cue, identify that cue and retain spoken content without a literal tag flag. `not_distinguished` and `uncertain_or_control_preferred` are unresolved, not definitive proof that a tag is unsupported. No-audio trials fail delivery outright. v2.5 and unknown-tag controls check audible words/content; no literal tag detected does not independently prove the internal stripping implementation.', '',
              f'In {s["stripping_controls"]["condition_cue_preferred"]}/{s["stripping_controls"]["assessed"]} documented stripping controls (v2.5/unknown tags), the model nevertheless preferred the tagged-condition delivery for the requested cue. Stochastic rendering and judge bias are not separated here; cue judgments are screening observations, not validated tag pass rates.', '',
              '## Naturalness and prosody screen','',
              f'Configured/returned audio judge: {", ".join(s["judge_returned_models"])}. {s["blind_judgments"]} blind clip assessments and {s["paired_judgments"]} paired comparisons. Rubric: 1 severe problems, 3 noticeable issues but understandable, 5 natural/appropriate/clear. Scores are one model’s provisional ratings, not human MOS or native-speaker approval. Existing human ratings and critical-term correctness remain unchanged.', '',
              '| Repeated untagged English prompts | Rated clips | Naturalness mean /5 | Prosody mean /5 | Intelligibility mean /5 |', '|---|---:|---:|---:|---:|']
    for r in s['rating_summary']:
        if r['scope']=='rest_three_prompts_three_repeats':lines.append(f'| {r["model"]} | {r["n"]} | {r["naturalness_mean"]:.2f} | {r["prosody_mean"]:.2f} | {r["intelligibility_mean"]:.2f} |')
    lines += ['', 'Three repeated texts and different voices prevent a general model-quality ranking. Per-clip reasons, observed delivery and blind transcripts are in `blind_ratings.csv`; per-tag comparisons are in `pair_ratings.csv` and `tag_evidence.csv`.', '',
              'A calibration clip deliberately adds an 80 ms tone and 900 ms silence before intact speech. The judge missed that planted gap, despite correctly transcribing the speech. It also did not flag the reconstructed stream gaps. Its silence/timing judgments therefore cannot validate playback or certify continuous audio. The negative control is unchanged speech. This two-control check does not calibrate all naturalness/emotion ratings; those remain screening observations.', '',
              '## Speed controls','', '| Model | Requested speed | Audio duration | Ratio to speed 1.0 |', '|---|---:|---:|---:|']
    for r in s['speed_controls']:lines.append(f'| {r["model"]} | {r["speed"]} | {r["duration_s"]:.3f} s | {r["duration_ratio"]:.3f} |')
    lines += ['', 'Single-trial durations move in the expected direction for both speeds/models; stochastic synthesis means exact reciprocal scaling is not established.', '',
              '## Empty audio and numeric readings','', '| Case | HTTP | Failure |', '|---|---:|---|']
    for r in s['unexpected_failures']:lines.append(f'| {r["case_id"]} | {r["actual_http"]} | 44-byte header, zero decoded PCM frames |')
    lines += ['', 'The eight rechecks yielded six valid clips and two further empty outputs. Some 24 kHz trials recover; one 48 kHz sigh trial still fails. A sample-rate change is not a consistent fix. Raw numeric text initially failed on v3.0; its 24 kHz recheck failed and 48 kHz recheck produced audio. Keep original attempts in the denominator.', '',
              '| Numeric case with audio | Blindly heard by the audio model |', '|---|---|']
    for m in metrics:
        if m['section']=='normalization' or m['case_id'].startswith('NF-C-3-raw-recheck'):
            heard=blind.get(m['case_id'],{}).get('heard','not assessed')
            lines.append(f'| {m["case_id"]} | {heard.replace("|","/")} |')
    lines += ['', 'Blind transcripts are provisional listening evidence. Do not infer correctness just from fluent audio. Continue explicitly verbalizing minus signs, leading-zero PIN digits and unambiguous times, followed by critical-slot verification.', '',
              '## Recommended changes and next validation','',
              '1. Decode and count PCM frames before declaring TTS success; reject header-only responses. Use bounded retries or a reviewed fallback while retaining first-attempt failures.',
              '2. For non-interactive files, REST avoids output-stream starvation but retains the full generation wait. For interactive pilots, consider the tested v2.5 configuration with queueing and connection reuse; validate larger paired traffic before selecting a model.',
              '3. Use only documented v3.0 tags. Test intended cues with the chosen voice/language; avoid assuming all tags deliver correctly merely because the request returns 200.',
              '4. Keep speed changes conservative; verify content and naturalness alongside pacing. Preserve explicit language and model-specific voices.',
              '5. Native listeners should review ambiguous tag effects, naturalness and critical numeric readings. Test an actual online jitter buffer and interruption behavior separately; the present reconstruction is not a handset/Exotel test.', '',
              '## Reproduce and inspect','',
              'Credit-free replay: `python run_evaluation.py --mode replay --part all --reports`. Standalone follow-up: `python scripts/analyze_timbre_followup.py`. Open `results/timbre_followup/index.html` for all successful clips and both playback reconstructions. Raw header-only WAVs and all request records are preserved in the same evidence folder.', '',
              'Optional new paid collection requires `python scripts/timbre_followup.py --live --judge-live`; cached successful requests/judgments are reused, and existing failed trials are retained rather than silently retried. The listed rechecks have their own IDs. `python scripts/judge_playback_checks.py --live` produces the separate playback/control screen. No API access is used by replay.', '']
    (P/'TIMBRE_FOLLOWUP.md').write_text('\n'.join(lines),encoding='utf8')


def analyze(project=None):
    global P
    if project is not None:P=Path(project)
    out=P/'results/timbre_followup'
    if not (P/'data/timbre_followup_cases.csv').exists():return None
    import timbre_followup as t
    t.P=P;t.OUT=out
    rows=read(P/'data/timbre_followup_cases.csv');records=t.chosen(rows)
    metrics=t.prepare_audio(rows,records)
    blind_rows=read(out/'blind_ratings.csv');pair_rows=read(out/'pair_ratings.csv')
    blind={r['case_id']:r for r in blind_rows};pairs={r['case_id']:r for r in pair_rows}
    metric_ids={r['case_id']:r for r in metrics}
    for r in blind_rows:
        if r['case_id'] not in metric_ids or r['audio_sha256']!=metric_ids[r['case_id']]['audio_sha256']:
            raise ValueError('Judge audio hash mismatch')
        if r['assessor']!='audio_model_provisional':raise ValueError('Judge provenance missing')
    latency=[]
    for model in ['timbre-v3.0','timbre-v2.5']:
        for length in ['short','medium','long']:
            group=[m for m in metrics if m['section']=='rest_latency' and m['model']==model and m['length']==length]
            if not group:continue
            times=[m['latency_ms'] for m in group]
            latency.append(dict(model=model,voice=group[0]['voice'],length=length,n=len(group),
                                text_characters=len(group[0]['input_text']),median_ms=statistics.median(times),
                                min_ms=min(times),max_ms=max(times),median_audio_s=statistics.median(m['duration_s'] for m in group)))
    write(out/'latency_summary.csv',latency)
    streams=reconstruct(records,out)
    tags=tag_evidence(metrics,blind,pairs);write(out/'tag_evidence.csv',tags)
    speed=[]
    for m in metrics:
        if m['section']=='speed':
            base=metric_ids[m['neutral_case_id']]
            speed.append(dict(case_id=m['case_id'],model=m['model'],speed=m['speed'],
                              duration_s=m['duration_s'],neutral_duration_s=base['duration_s'],
                              duration_ratio=m['duration_s']/base['duration_s']))
    write(out/'speed_controls.csv',speed)
    ratings=[]
    for model in ['timbre-v3.0','timbre-v2.5']:
        group=[r for r in blind_rows if r['model']==model]
        neutral=[r for r in group if r['section']=='neutral_style']
        repeats=[r for r in group if r['section']=='rest_latency']
        for label,selection in [('all_conditions',group),('neutral_en_hi_only',neutral),('rest_three_prompts_three_repeats',repeats)]:
            if selection:ratings.append(dict(model=model,scope=label,n=len(selection),
                naturalness_mean=statistics.mean(float(r['naturalness_1to5']) for r in selection),
                prosody_mean=statistics.mean(float(r['prosody_1to5']) for r in selection),
                intelligibility_mean=statistics.mean(float(r['intelligibility_1to5']) for r in selection),
                interpretation='One audio-model screen, not human MOS; mixed voice/text/condition convenience sample'))
    write(out/'rating_summary.csv',ratings)
    rest=[m for m in metrics if m['transport']=='REST']
    early=[m['case_id'] for m in rest if m['early_gap_candidate']]
    judged_early=[m['case_id'] for m in rest if yes(blind.get(m['case_id'],{}).get('initial_sound_then_unexpected_silence'))]
    both=sorted(set(early)&set(judged_early))
    failed=[dict(case_id=r['case_id'],expected_http=r['expected_http'],actual_http=records.get(r['case_id'],{}).get('http_status'),
                 ok=records.get(r['case_id'],{}).get('ok',False),error=records.get(r['case_id'],{}).get('error'))
            for r in rows if not records.get(r['case_id'],{}).get('ok')]
    usage=[json.loads(p.read_text(encoding='utf8')) for p in (out/'judge').rglob('*.json')]
    playback_checks=read(out/'playback_judge_checks.csv')
    controls=[r for r in playback_checks if r['kind'] in ['synthetic_positive_control','unchanged_negative_control']]
    control_results=[dict(id=r['id'],expected_initial_gap=r['kind']=='synthetic_positive_control',
                         detected_initial_gap=yes(r['initial_sound_then_unexpected_silence']),
                         passed=yes(r['initial_sound_then_unexpected_silence'])==(r['kind']=='synthetic_positive_control')) for r in controls]
    raw_attempts=t.attempts()
    unique_requests={r['request_id']:r for r in raw_attempts}
    eligible_pairs=sum(bool(m['neutral_case_id']) and m['neutral_case_id'] in metric_ids for m in metrics)
    s=dict(status='completed' if len(records)==len(rows) and len(blind)==len(metrics) and len(pairs)==eligible_pairs else 'partial',
           new_api_calls_in_replay=0,planned_cases=len(rows),attempted_cases=len(records),valid_audio_clips=len(metrics),
           rest_valid_clips=len(rest),expected_rejections=[r for r in failed if int(r['expected_http'])>=400 and int(r['expected_http'])==r['actual_http']],
           unexpected_failures=[r for r in failed if int(r['expected_http'])<400 or int(r['expected_http'])!=r['actual_http']],
           rest_latency=latency,fresh_streams=streams,speed_controls=speed,
           judge_models=sorted(set(r['judge_model'] for r in blind_rows)),judge_returned_models=sorted(set(str(r.get('returned_model')) for r in usage)),
           blind_judgments=len(blind),paired_judgments=len(pairs),eligible_audio_pairs=eligible_pairs,rating_summary=ratings,
           playback_judgments=len(playback_checks),judge_gap_control_results=control_results,
           judge_gap_controls_all_passed=bool(control_results) and all(r['passed'] for r in control_results),
           http_requests=len({r['request_id'] for r in raw_attempts}),
           http_status_counts=dict(Counter(str(r.get('http_status')) for r in unique_requests.values())),
           transient_http_failures=[dict(case_id=r['case_id'],attempt=r.get('attempt'),http_status=r.get('http_status'),error=r.get('error'))
                                    for r in unique_requests.values() if r.get('http_status') is None or r.get('http_status')>=500],
           collection_first_utc=min((r['started_at'] for r in raw_attempts if r.get('started_at')),default=None),
           collection_last_utc=max((r['started_at'] for r in raw_attempts if r.get('started_at')),default=None),
           tag_counts=dict(Counter(r['status'] for r in tags)),
           stripping_controls=dict(assessed=sum(r['documented_policy']!='render_tag' and r['status']!='not_assessed' for r in tags),
                                   condition_cue_preferred=sum(r['documented_policy']!='render_tag' and r['condition_cue_preferred'] for r in tags)),
           v3_supported_tag_screen=dict(Counter(r['status'] for r in tags if r['documented_policy']=='render_tag')),
           rest_early_gap_energy_flags=early,rest_initial_gap_judge_flags=judged_early,rest_initial_gap_both_flags=both,
           judge_usage=dict(cached_successful_responses=len(usage),prompt_tokens=sum(r.get('prompt_tokens') or 0 for r in usage),
                            output_tokens=sum(r.get('output_tokens') or 0 for r in usage),thought_tokens=sum(r.get('thought_tokens') or 0 for r in usage)),
           boundaries=['REST full-body dispatch timer is not TTFA; completed PCM cannot have network-arrival underruns.',
                       'SSE quality judgments initially hear concatenated PCM; separately rendered immediate playback retains measured network gaps.',
                       'Different model voice catalogs prevent same-voice isolation. Three sequential repeats per length/model, fixed v3/v2.5 order; region/load/cold state uncontrolled.',
                       'Energy thresholds -35/-45/-55 dBFS at 10 ms are flags, not perceptual silence or stall ground truth.',
                       'Single audio-model ratings and cue comparisons are provisional; not human MOS or native-speaker verification.',
                       'Provider documentation describes features; this test cannot prove deployment dates or a provider-side fix.'])
    (out/'summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    cards=[]
    for m in metrics:
        b=blind.get(m['case_id'],{});p=pairs.get(m['case_id'],{})
        card=f'<section><h2>{html.escape(m["case_id"])} · {html.escape(m["model"])} / {html.escape(m["voice"])}</h2>'
        card+=f'<p>{html.escape(m["input_text"])}</p><p>Full-response latency {m["latency_ms"]:.1f} ms; decoded duration {m["duration_s"]:.2f} s. {html.escape(m["transport"])}</p>'
        card+=f'<audio controls preload="none" src="listen/{m["case_id"]}.wav"></audio>'
        if b:card+=f'<p>Audio-model screen: naturalness {b["naturalness_1to5"]}/5; prosody {b["prosody_1to5"]}/5. Heard: {html.escape(b["heard"])}. {html.escape(b["reason"])}</p>'
        if p:card+=f'<p>Paired cue assessment: {html.escape(p["more_cue"])} (condition {p["condition_side"]}). {html.escape(p["reason"])}</p>'
        stream=next((x for x in streams if x['case_id']==m['case_id']),None)
        if stream:
            card+=f'<p>Sample-verified immediate playback: {stream["underruns"]} underruns, {stream["starvation_s"]:.3f} s starvation. Initial zeros represent dispatch wait.</p><audio controls preload="none" src="{stream["immediate_path"]}"></audio>'
            card+=f'<p>Future-aware delayed reconstruction:</p><audio controls preload="none" src="{stream["delayed_path"]}"></audio>'
        cards.append(card+'</section>')
    failed_cards='<h2>HTTP-200 synthesis failures</h2><p>Each file below is only a WAV header, with zero decoded samples. These are preserved failures, not playable speech.</p><ul>'
    for failure in s['unexpected_failures']:
        record=records[failure['case_id']];path=Path(record['audio_path']).relative_to(out.relative_to(P)).as_posix()
        failed_cards+=f'<li>{html.escape(failure["case_id"])}: <a href="{path}">original header-only WAV</a></li>'
    failed_cards+='</ul><h2>Judge calibration controls</h2><p>The model missed the planted initial tone + 900 ms gap. Its timing judgments cannot certify continuous playback.</p>'
    for control in controls:
        path=Path(control['audio_path']).relative_to(out.relative_to(P)).as_posix()
        failed_cards+=f'<p>{html.escape(control["id"])}: known inserted gap {control["known_inserted_gap_s"]} s; judge flag {control["initial_sound_then_unexpected_silence"]}.</p><audio controls preload="none" src="{path}"></audio>'
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Timbre follow-up evidence</title><style>body{font:16px system-ui;max-width:1000px;margin:30px auto;padding:12px}section{border-top:1px solid #aaa;padding:12px 0}audio{width:100%}</style><h1>Timbre 3.0 / 2.5 follow-up</h1><p>Saved live API outputs and separate provisional audio-model judgments. Scores are not human MOS. REST response delay, waveform pauses and streaming underruns are different measurements. Neutral/tag comparisons hide model/condition order during judging.</p><p><a href="../../TIMBRE_FOLLOWUP.md">Detailed findings and recommendations</a></p>'+failed_cards+''.join(cards),encoding='utf8')
    markdown_report(s,metrics,blind,tags)
    return s


if __name__=='__main__':
    s=analyze();print(json.dumps(s,ensure_ascii=False,indent=2))
