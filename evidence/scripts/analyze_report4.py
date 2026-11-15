"""Replay Report-4 request, duration/RTF and buffering evidence without API calls."""
import csv,hashlib,html,json,statistics,sys,wave
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'scripts'))


def read(path):
    if not Path(path).exists():return []
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def write(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)


def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def logs(path):return [json.loads(x) for x in path.read_text(encoding='utf8').splitlines() if x.strip()] if path.exists() else []
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path):
    x,sr=sf.read(path,dtype='int16',always_2d=True)
    return dict(decoded_pcm_samples=int(x.size),decoded_frames=len(x),channels=x.shape[1],sample_rate=sr,
                audio_duration_s=len(x)/sr,peak=int(np.max(np.abs(x.astype(np.int32)))) if x.size else 0),x


def merge(records):
    unique={}
    for r in records:
        if not r.get('request_id'):continue
        unique[r['request_id']]={**unique.get(r['request_id'],{}),**r}
    return list(unique.values())


def attempt_ledger(project,records,cohort,protocol=None):
    cases={r['case_id']:r for r in read(project/'data/timbre_followup_cases.csv')}
    for name in ['tts_quality_manifest.csv','tts_rewrite_manifest.csv']:
        cases.update({r['case_id']:dict(input_text=r['text'],expected_http='200',phase='heldout_listening' if 'quality' in name else 'heldout_rewrite') for r in read(project/'data/report4'/name)})
    if protocol:
        cases.update({r['case_id']:dict(input_text=r['text'],expected_http='200',phase=r['phase'],length=r['length']) for r in protocol['rest_order']})
    groups=defaultdict(list)
    for r in merge(records):
        if r.get('kind') in ['tts','tts_stream']:groups[r['case_id']].append(r)
    output=[]
    for cid,group in groups.items():
        local=[];previous=None
        for record in group:
            settings=record['settings'];config=settings['audio_config'];case=cases.get(cid,{})
            text=record.get('input_text',case.get('input_text'))
            if text is None and protocol:
                prompt=next((p for p in protocol['prompts'] if p['length'] in cid),protocol['prompts'][0])
                text=prompt['text']
            if text is None:raise ValueError('Cannot identify request text: '+cid)
            body=project/record['audio_path'] if record.get('audio_path') else project/record['raw_path'] if record.get('raw_path') else None
            stats=dict(decoded_pcm_samples=0,decoded_frames=0,channels=0,sample_rate=config['sample_rate'],audio_duration_s=0.,peak=0)
            status=record.get('http_status');error=record.get('error','');outcome='transport_error' if status is None else 'http_error'
            is_sse=record.get('kind')=='tts_stream'
            if status==200:
                try:
                    stats,_=decode(body)
                    outcome='valid_pcm' if stats['decoded_pcm_samples']>0 and stats['peak']>=33 else 'empty_pcm' if not stats['decoded_pcm_samples'] else 'silent_pcm'
                    if is_sse and not record.get('ok'):outcome='incomplete_stream'
                except Exception as exc:outcome='invalid_audio';error=type(exc).__name__
            is_retry=int(record.get('attempt',1))>1
            backoff=max(0,float(record.get('retry_inclusive_ms') or record['latency_ms'])-float(previous.get('retry_inclusive_ms') or previous['latency_ms'])-record['latency_ms']) if is_retry and previous else 0
            phase=case.get('phase','warmup_rest' if cid.startswith('R4-WARM') else 'replacement_rest' if cid.startswith('R4-REPLACE') else 'followup')
            if cohort=='timbre_followup':phase='explicit_recheck' if '-recheck-' in cid else 'initial_followup'
            row=dict(cohort=cohort,phase=phase,case_id=cid,attempt_id=record['request_id'],retry_of=previous['request_id'] if is_retry and previous else '',
                     recheck_of=cid.split('-recheck-')[0] if '-recheck-' in cid else '',
                     version=settings['model'],voice_id=settings['voice'],input_text=text,input_chars=len(text),input_words=len(text.split()),
                     text_hash=hashlib.sha256(text.encode('utf8')).hexdigest(),request_fingerprint=record.get('fingerprint'),
                     endpoint=settings['endpoint'],language=settings['language'],speed=settings['speed'],sample_rate=config['sample_rate'],
                     encoding=config['encoding'],container=config['container'],http_status=status,
                     error_code='' if outcome=='valid_pcm' else 'HTTP_'+str(status) if outcome=='http_error' else outcome.upper(),
                     error_code_origin='client classification; provider-specific code unavailable when absent',error_detail=error,
                     transport='SSE' if is_sse else 'REST',body_bytes=None if is_sse else body.stat().st_size if body and body.exists() else 0,
                     saved_audio_bytes=body.stat().st_size if body and body.exists() and status==200 else None,
                     body_representation='decoded SSE PCM remux; wire body size not recorded' if is_sse else 'original HTTP response body',
                     body_path=body.relative_to(project).as_posix() if body else '',
                     body_sha256=sha(body) if body and body.exists() else '',decoded_pcm_samples=stats['decoded_pcm_samples'],decoded_frames=stats['decoded_frames'],
                     duration_s=stats['audio_duration_s'],decoded_sample_rate=stats['sample_rate'],
                     latency_ms=record['latency_ms'],request_total_ms=record['latency_ms'],
                     rtf_client=record['latency_ms']/1000/stats['audio_duration_s'] if stats['audio_duration_s'] else None,
                     retry_backoff_ms=backoff,scheduled_retry_backoff_ms=(2**(int(record['attempt'])-2)*1000) if is_retry else 0,
                     retry_inclusive_ms=record.get('retry_inclusive_ms'),attempt_number=record.get('attempt'),attempt_outcome=outcome,
                     expected_http=int(case.get('expected_http') or 200),started_at=record.get('started_at'),
                     region='not supplied by recorded API metadata',first_byte_ms='not collected',channels=config['num_channels'],sample_width=config['sample_width'])
            local.append(row);previous=record
        last=local[-1]
        final='recovered_on_retry' if last['attempt_outcome']=='valid_pcm' and len(local)>1 else 'success' if last['attempt_outcome']=='valid_pcm' else 'expected_rejection' if last['expected_http']>=400 and last['http_status']==last['expected_http'] else 'persistent_empty' if last['attempt_outcome'] in ['empty_pcm','silent_pcm'] else 'http_failure'
        for row in local:row.update(final_case_outcome=final,case_attempts=len(local),retries=len(local)-1)
        output.extend(local)
    return output


def counts(rows):
    final={r['case_id']:r for r in rows};n=len(final);good=sum(r['attempt_outcome']=='valid_pcm' for r in rows);eventual=sum(r['attempt_outcome']=='valid_pcm' for r in final.values())
    exclusions=sum(r['expected_http']>=400 for r in final.values())
    return dict(cases=n,http_attempts=len(rows),valid_pcm_attempts=good,disjoint_attempt_outcomes=dict(Counter(r['attempt_outcome'] for r in rows)),
                http_status_counts=dict(Counter(str(r['http_status']) for r in rows)),eventual_success_cases=eventual,
                attempt_success_rate=good/len(rows) if rows else None,eventual_case_success_rate=eventual/n if n else None,
                positive_case_success_rate=eventual/(n-exclusions) if n>exclusions else None,expected_rejections=exclusions,
                retry_attempts=sum(bool(r['retry_of']) for r in rows),explicit_recheck_cases=sum(bool(r['recheck_of']) for r in final.values()),
                final_case_outcomes=dict(Counter(r['final_case_outcome'] for r in final.values())))


def rest_analysis(project,out,rows):
    final={r['case_id']:r for r in rows if r['cohort']=='report4_controlled' and r['phase'] in ['measured_rest','replacement_rest']}
    trials=[]
    for row in rows:
        if row['cohort']!='report4_controlled' or row['phase'] not in ['measured_rest','replacement_rest']:continue
        length=next(s for s in ['short','medium','long'] if s in row['case_id'])
        r={**row,'length':length,'eligible_primary':final[row['case_id']]['attempt_id']==row['attempt_id'] and row['attempt_outcome']=='valid_pcm'}
        if r['eligible_primary']:
            stats,x=decode(project/r['body_path']);canonical=out/'listen'/(r['case_id']+'.wav');canonical.parent.mkdir(exist_ok=True)
            if not canonical.exists():sf.write(canonical,x,stats['sample_rate'],subtype='PCM_16')
            r.update(audio_path=canonical.relative_to(project).as_posix(),audio_sha256=sha(canonical))
        trials.append(r)
    write(out/'rest_latency_trials.csv',trials)
    summary=[]
    for model in ['timbre-v3.0','timbre-v2.5']:
        for length in ['short','medium','long']:
            group=[r for r in trials if r['version']==model and r['length']==length];valid=[r for r in group if r['eligible_primary']]
            if not valid:continue
            row=dict(model=model,voice=valid[0]['voice_id'],length=length,input_chars=valid[0]['input_chars'],input_words=valid[0]['input_words'],
                     successful_trials=len(valid),attempts=len(group),case_trials=len({r['case_id'] for r in group}),
                     attempt_success_rate=sum(r['attempt_outcome']=='valid_pcm' for r in group)/len(group),
                     eventual_case_success_rate=len(valid)/len({r['case_id'] for r in group}))
            for field in ['request_total_ms','duration_s','rtf_client']:
                values=[r[field] for r in valid];row.update({field+'_median':statistics.median(values),field+'_min':min(values),field+'_max':max(values)})
            summary.append(row)
    write(out/'rest_latency_summary.csv',summary);return trials,summary


def streaming(project,out,records):
    from validate_playback import schedule,render
    collected=merge(records);chosen={}
    for r in collected:
        if not r.get('timeline_path') or not r.get('audio_path'):continue
        if r['case_id'].startswith(('N8-','NF-S-','R4-WS-','R4-WARM-WS-')):chosen[r['request_id']]=r
    chunks_export=[];sensitivity=[];trials=[];replays=[]
    for r in chosen.values():
        source=project/r['audio_path'];stats,x=decode(source);rate=stats['sample_rate']
        chunks=json.loads((project/r['timeline_path']).read_text())['chunks'];lengths=[c['bytes']//2 for c in chunks]
        if any(c['bytes']%2 for c in chunks) or sum(lengths)!=len(x):raise ValueError('Chunk/PCM byte mismatch: '+r['case_id'])
        arrivals=[round(c['t_s']*rate) for c in chunks];base=schedule(arrivals,lengths,rate)
        cohort='original_N8' if r['case_id'].startswith('N8') else 'fresh_SSE' if r['case_id'].startswith('NF') else 'report4_WS'
        phase='cold_warmup' if r['case_id'].startswith('R4-WARM') else 'warm_measured' if r['case_id'].startswith('R4-WS') else 'saved_trace'
        trials.append(dict(cohort=cohort,phase=phase,case_id=r['case_id'],request_id=r['request_id'],model=r['settings']['model'],voice=r['settings']['voice'],
                           ok=r['ok'],connection=r.get('connection','HTTP SSE'),connect_ms=r.get('connect_ms'),
                           observed_ttfa_ms=r.get('ttfa_ms'),request_total_ms=r['latency_ms'],audio_duration_s=stats['audio_duration_s'],
                           rtf_client=r['latency_ms']/1000/stats['audio_duration_s'],chunks=len(chunks),decoded_pcm_samples=stats['decoded_pcm_samples'],
                           audio_path=r['audio_path'],audio_sha256=sha(source),timeline_path=r['timeline_path'],timeline_sha256=sha(project/r['timeline_path'])))
        end=arrivals[0];cumulative=0
        for index,(c,arrival,n) in enumerate(zip(chunks,arrivals,lengths)):
            before=max(0,end-arrival);starve=max(0,arrival-end) if index else 0;end=max(end,arrival)+n;cumulative+=n
            chunks_export.append(dict(cohort=cohort,phase=phase,case_id=r['case_id'],request_id=r['request_id'],model=r['settings']['model'],
                                      chunk_index=index,arrival_s=c['t_s'],arrival_sample=arrival,pcm_samples=n,sample_rate=rate,
                                      chunk_duration_s=n/rate,cumulative_received_audio_s=cumulative/rate,
                                      playable_buffer_before_s=before/rate,playable_buffer_after_s=(before+n)/rate,
                                      zero_buffer_starvation_s=starve/rate))
        for buffer in [0,50,100,200,500,1000]:
            start=arrivals[0]+round(buffer*rate/1000)
            for tolerance in [1,10,20]:
                result=schedule(arrivals,lengths,rate,start=start,tolerance_ms=tolerance)
                sensitivity.append(dict(cohort=cohort,phase=phase,case_id=r['case_id'],request_id=r['request_id'],model=r['settings']['model'],
                                        initial_buffer_ms=buffer,tolerance_ms=tolerance,observed_ttfa_ms=r['ttfa_ms'],
                                        simulated_startup_ms=start/rate*1000,underflow_count=len(result['gaps']),
                                        total_starvation_ms=sum(n/rate*1000 for _,n in result['all_gaps']),
                                        retrospective_extra_wait_ms=(base['earliest_start']-arrivals[0])/rate*1000,
                                        retrospective_policy='future-aware bound, not measured online TTFA'))
            if r['case_id'] in ['NF-S-3-short','NF-S-25-short'] and buffer in [0,500,1000]:
                path=out/'playback'/f'{r["case_id"]}__buffer_{buffer}.wav';path.parent.mkdir(exist_ok=True)
                result=schedule(arrivals,lengths,rate,start=start)
                render(path,x[:,0].astype('<i2').tobytes(),lengths,result['starts'],rate)
                replays.append(dict(case_id=r['case_id'],model=r['settings']['model'],buffer_ms=buffer,underflows=len(result['gaps']),
                                    starvation_ms=sum(n/rate*1000 for _,n in result['all_gaps']),path=path.relative_to(out).as_posix()))
    write(out/'stream_chunk_timeline.csv',chunks_export);write(out/'stream_trials.csv',trials);write(out/'buffer_sensitivity.csv',sensitivity)
    groups=[]
    for key in sorted(set((r['cohort'],r['phase'],r['model'],r['initial_buffer_ms']) for r in sensitivity)):
        selected=[r for r in sensitivity if (r['cohort'],r['phase'],r['model'],r['initial_buffer_ms'])==key and r['tolerance_ms']==1]
        groups.append(dict(cohort=key[0],phase=key[1],model=key[2],buffer_ms=key[3],streams=len(selected),
                           streams_with_underflows=sum(r['underflow_count']>0 for r in selected),
                           starvation_ms_median=statistics.median(r['total_starvation_ms'] for r in selected),
                           simulated_startup_ms_median=statistics.median(r['simulated_startup_ms'] for r in selected)))
    write(out/'buffer_summary.csv',groups);write(out/'playback_examples.csv',replays)
    ws=[]
    for model in ['timbre-v3.0','timbre-v2.5']:
        g=[r for r in trials if r['cohort']=='report4_WS' and r['phase']=='warm_measured' and r['model']==model]
        valid=[r for r in g if r['ok']]
        if valid:ws.append(dict(model=model,prompt_length='short',successful_trials=len(valid),attempted_trials=len(g),
                                ttfa_ms_median=statistics.median(r['observed_ttfa_ms'] for r in valid),
                                ttfa_ms_min=min(r['observed_ttfa_ms'] for r in valid),ttfa_ms_max=max(r['observed_ttfa_ms'] for r in valid)))
    return dict(streams=len(trials),chunk_rows=len(chunks_export),sensitivity_rows=len(sensitivity),buffers_ms=[0,50,100,200,500,1000],
                tolerances_ms=[1,10,20],buffer_summary=groups,warm_ws=ws,playback_examples=replays)


def plots(out,summary,stream):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,3,figsize=(12,3.5),layout='constrained')
    for model,color in [('timbre-v3.0','#a34a14'),('timbre-v2.5','#096b5d')]:
        g=sorted((r for r in summary if r['model']==model),key=lambda r:r['input_chars']);x=[r['input_chars'] for r in g]
        for ax,field,label,div in zip(axes,['request_total_ms','duration_s','rtf_client'],['REST full-response time (s)','Decoded audio duration (s)','Client RTF'],[1000,1,1]):
            y=[r[field+'_median']/div for r in g];err=[[a-r[field+'_min']/div for a,r in zip(y,g)],[r[field+'_max']/div-a for a,r in zip(y,g)]]
            ax.errorbar(x,y,yerr=err,marker='o',capsize=3,label=model,color=color);ax.set_xlabel('Input characters');ax.set_ylabel(label);ax.grid(alpha=.15)
    axes[0].legend();fig.suptitle('Controlled matched-input trial: medians and full ranges; different voices')
    fig.savefig(out/'rest_duration_rtf.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
    for model,color in [('timbre-v3.0','#a34a14'),('timbre-v2.5','#096b5d')]:
        g=[r for r in stream['buffer_summary'] if r['cohort']=='fresh_SSE' and r['model']==model]
        axes[0].plot([r['buffer_ms'] for r in g],[r['streams_with_underflows'] for r in g],marker='o',color=color,label=model)
        axes[1].plot([r['buffer_ms'] for r in g],[r['starvation_ms_median'] for r in g],marker='o',color=color,label=model)
    for ax,label in zip(axes,['Streams with underruns (of 3)','Median physical starvation (ms)']):ax.set_xlabel('Fixed initial prebuffer (ms)');ax.set_ylabel(label);ax.grid(alpha=.15)
    axes[0].legend();fig.suptitle('Saved fresh SSE traces: fixed-buffer replay; 1 ms reporting tolerance')
    fig.savefig(out/'buffer_tradeoff.png',dpi=160);plt.close(fig)


def build_page(project,out,s):
    def table(head,rows):return '<table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table>'
    contents='<h1>Final controlled timing and reliability checks</h1><p>Report-4 extension · 15 November 2026. Saved measurements and offline replays; no live API access is needed to view this page.</p>'
    contents+='<h2>Controlled REST timing</h2><p>Same three input strings; balanced seeded order, one request at a time, separate warm-ups. Catalog voices Tarika and Kaveri differ. Values below are dispatch to complete HTTP body, not TTFA.</p>'
    contents+=table(['Model / length','Successful / attempts','Response median (range), s','Audio median, s','RTF median'],[[r['model']+' / '+r['length'],f'{r["successful_trials"]}/{r["attempts"]}',f'{r["request_total_ms_median"]/1000:.3f} ({r["request_total_ms_min"]/1000:.3f}–{r["request_total_ms_max"]/1000:.3f})',f'{r["duration_s_median"]:.2f}',f'{r["rtf_client_median"]:.3f}'] for r in s['controlled_rest']])
    contents+='<img alt="Input length versus REST latency, output duration and client RTF with full-range error bars" src="rest_duration_rtf.png"><p>Higher client RTF on these inputs is consistent with slower end-to-end delivery per second of generated audio. It cannot isolate GPU compute, server queues or network overhead; the cause remains unresolved.</p>'
    contents+='<h2>Attempt-level outcome audit</h2>'+table(['Cohort','Cases','HTTP attempts','Valid PCM attempts','Attempt success','Eventual case success','Outcomes'],[[k,r['cases'],r['http_attempts'],r['valid_pcm_attempts'],f'{r["attempt_success_rate"]:.2%}',f'{r["eventual_case_success_rate"]:.2%}',json.dumps(r['disjoint_attempt_outcomes'])] for k,r in s['http_cohorts'].items()])
    contents+='<p>Rates include diagnostic and expected-negative cases; they are not population reliability estimates. Separate rechecks retain their own case IDs. Header-only empty audio and placeholder length headers with valid PCM are different outcomes. <a href="tts_http_attempts.csv">Attempt ledger</a> · <a href="rest_latency_trials.csv">REST trials</a>.</p>'
    contents+='<h2>Separate warm WebSocket timing</h2>'+table(['Model','Successful / attempted','TTFA median, ms','Range, ms'],[[r['model'],f'{r["successful_trials"]}/{r["attempted_trials"]}',f'{r["ttfa_ms_median"]:.1f}',f'{r["ttfa_ms_min"]:.1f}–{r["ttfa_ms_max"]:.1f}'] for r in s['streaming']['warm_ws']])
    contents+='<p>Short prompt only; cold connection and its first warm-up request are excluded. TTFA is measured first playable PCM, not semantic speech onset and not a retrospective stall-free start.</p><h2>Buffer versus starvation</h2><img alt="Fresh SSE buffer-versus-underflow and starvation tradeoff" src="buffer_tradeoff.png"><p>Fixed 0/50/100/200/500/1000 ms startup prebuffers are replayed on saved arrivals. Future-aware minimum gap-free start is separately labeled. This does not certify handset playback or interruption cleanup.</p>'
    for r in s['streaming']['playback_examples']:
        contents+=f'<section><h3>{html.escape(r["model"])} · short · {r["buffer_ms"]} ms prebuffer</h3><p>{r["underflows"]} underruns; {r["starvation_ms"]:.1f} ms starvation.</p><audio controls preload="none" src="{r["path"]}"></audio></section>'
    contents+='<p><a href="stream_chunk_timeline.csv">Chunk arrival and buffer ledger</a> · <a href="buffer_sensitivity.csv">All replay conditions</a> · <a href="../../REPORT4_IMPLEMENTATION.md">Implementation status and pending listening work</a></p>'
    (out/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Report 4 verification</title><style>body{font:16px/1.55 system-ui;max-width:1100px;margin:30px auto;padding:18px;color:#183247}table{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto}td,th{text-align:left;border-bottom:1px solid #cddbe3;padding:8px}th{background:#ecf2f6}img{max-width:100%;margin:15px 0}section{display:inline-block;vertical-align:top;width:46%;margin:1%;padding:10px;background:#f0f5f7}audio{width:100%}@media(max-width:600px){section{width:100%}}</style>'+contents+'</html>',encoding='utf8')


def analyze(project=None):
    project=Path(project or P);out=project/'results/report4';protocol_path=out/'protocol.json'
    if not protocol_path.exists():return None
    protocol=json.loads(protocol_path.read_text(encoding='utf8'));controlled=logs(out/'attempts.jsonl');followup=logs(project/'results/timbre_followup/attempts.jsonl')
    optional=logs(project/'results/report4_quality/attempts.jsonl')
    all_http=attempt_ledger(project,followup,'timbre_followup')+attempt_ledger(project,controlled,'report4_controlled',protocol)+attempt_ledger(project,optional,'report4_quality')
    write(out/'tts_http_attempts.csv',all_http);trials,rest=rest_analysis(project,out,all_http)
    stream=streaming(project,out,logs(project/'results/next/attempts.jsonl')+followup+controlled)
    success=all(r['successful_trials']>=5 for r in rest) and len(rest)==6
    s=dict(status='controlled_collection_complete' if success else 'partial_controlled_collection',new_api_calls_in_replay=0,
           controlled_rest=rest,http_cohorts={c:counts([r for r in all_http if r['cohort']==c]) for c in ['timbre_followup','report4_controlled','report4_quality'] if any(r['cohort']==c for r in all_http)},streaming=stream,
           protocol_sha256=sha(protocol_path),latency_cause='unresolved: no provider traces to isolate compute, queueing, processing stages or transport overhead',
           voice_limitation='Tarika and Kaveri differ; matched text/language/speed/rate/client do not isolate a model-only effect',
           scope='Original ASR/human TTS scores, prior 66 valid follow-up clips, and new controlled timing collection remain separate.')
    if success:plots(out,rest,stream)
    dump(out/'summary.json',s)
    if success:build_page(project,out,s)
    return s


if __name__=='__main__':
    s=analyze();print(json.dumps(s,ensure_ascii=False,indent=2))
