"""Reproduce streaming and request diagnostics from saved events; never makes calls."""
from collections import defaultdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P))
from run_evaluation import load, logs, write_csv


def playback(chunks):
    end=None;stalls=0;silence=0.;offset=0.;start=0.
    for c in chunks:
        if end is None:end=c['t_s']+c['dur_s']
        else:
            if c['t_s']>end+.001:
                stalls+=1;silence+=c['t_s']-end;end=c['t_s']
            end+=c['dur_s']
        start=max(start,c['t_s']-offset);offset+=c['dur_s']
    return dict(stalls=stalls,stall_s=round(silence,3),stall_free_start_ms=round(start*1000,1))


def audit(out):
    all_records=[]
    for file in ['results/attempts.jsonl','results/next/attempts.jsonl']:
        records=logs(file)
        unique={}
        for i,r in enumerate(records):
            key=r.get('request_id') or (r.get('kind'),r.get('case_id'),r.get('run_tag'),r.get('started_at'),r.get('attempt',i))
            unique[key]=r
        for r in unique.values():
            if r.get('case_id','').startswith('CALL-'):continue
            settings=r.get('settings',{})
            all_records.append(dict(log=file,kind=r['kind'],case_id=r['case_id'],run_tag=r.get('run_tag',''),
                                    request_id=r.get('request_id',''),server_request_id=r.get('server_request_id',''),
                                    started_at_utc=r.get('started_at',''),http_status=r.get('http_status',''),
                                    success=r.get('ok',False),attempt=r.get('attempt',1),
                                    retry_count=max(0,r.get('attempt',1)-1),latency_ms=r.get('latency_ms',''),
                                    retry_inclusive_ms=r.get('retry_inclusive_ms',''),error=r.get('error') or '',
                                    model=settings.get('model',''),voice=settings.get('voice',''),
                                    request_settings=json.dumps(settings,ensure_ascii=False,sort_keys=True),
                                    raw_path=r.get('raw_path',''),timeline_path=r.get('timeline_path','')))
    write_csv(out/'request_attempts.csv',all_records)
    n8={}
    for r in logs('results/next/attempts.jsonl'):
        if r.get('kind')=='tts_stream' and r.get('case_id','').startswith('N8-') and r.get('ok'):
            n8[r['case_id'],r['run_tag']]=r
    timeline_rows=[];stream_rows=[]
    for r in n8.values():
        timeline=load(r['timeline_path']);chunks=timeline['chunks'];recomputed=playback(chunks)
        if not chunks:raise ValueError('Successful stream without chunks')
        if recomputed['stalls']!=r['stalls'] or abs(recomputed['stall_free_start_ms']-r['stall_free_start_ms'])>1.0:
            raise ValueError(f'Stream diagnostic reconciliation failed: {r["case_id"]}/{r["run_tag"]}')
        ttfa=chunks[0]['t_s']*1000
        stream_rows.append(dict(case_id=r['case_id'],run_tag=r['run_tag'],model=r['settings']['model'],voice=r['settings']['voice'],
                                sample_rate_hz=r['settings']['audio_config']['sample_rate'],
                                first_audio_ms=ttfa,complete_event_ms=r.get('complete_ms'),
                                total_generation_ms=r['latency_ms'],audio_duration_s=r['audio_duration_s'],
                                extra_wait_ms=recomputed['stall_free_start_ms']-ttfa,timeline_path=r['timeline_path'],**recomputed))
        for c in chunks:timeline_rows.append(dict(case_id=r['case_id'],run_tag=r['run_tag'],model=r['settings']['model'],**c))
    write_csv(out/'streaming_diagnostics.csv',stream_rows)
    write_csv(out/'streaming_chunk_timestamps.csv',timeline_rows)
    groups=defaultdict(list);finished=set();terminal=[]
    for r in all_records:
        if r['case_id'].startswith('N9-') and r['run_tag'].startswith('c'):
            identity=(r['kind'],r['run_tag'])
            if identity in finished:continue
            groups[r['kind'],r['run_tag'].split('_')[0]].append(r)
            if r['success'] or r['attempt']>=4 or (r['http_status'] not in ['',None,429,500,502,503,504]):
                finished.add(identity)
                terminal.append(r)
    capacity=[]
    for (kind,group),records in sorted(groups.items()):
        events=[]
        for r in records:
            start=datetime.fromisoformat(r['started_at_utc'])
            end=start+timedelta(milliseconds=float(r['latency_ms']))
            events.extend([(start,1),(end,-1)])
        inflight=peak=0
        for _,delta in sorted(events):inflight+=delta;peak=max(peak,inflight)
        outcomes=[r for r in terminal if r['kind']==kind and r['run_tag'].split('_')[0]==group]
        capacity.append(dict(kind=kind,requested_parallelism=int(group[1:]),max_http_attempts_inflight=peak,
                             attempt_rows=len(records),http_429_attempts=sum(r['http_status']==429 for r in records),
                             completed_requests=len(outcomes),successful_requests=sum(r['success'] for r in outcomes),retried_requests=sum(r['attempt']>1 for r in outcomes),
                             definition='first experiment round only; client dispatch-to-full-body intervals; excludes backoff; no provider queue visibility'))
    write_csv(out/'concurrency_diagnostics.csv',capacity)
    timestamps=[r['started_at_utc'] for r in all_records if r['started_at_utc']]
    soak=[];soak_seen=set()
    for r in all_records:
        identity=(r['kind'],r['run_tag'])
        if not r['case_id'].startswith('N9-') or not r['run_tag'].startswith('soak_') or identity in soak_seen:continue
        if r['success'] or r['attempt']>=4 or (r['http_status'] not in ['',None,429,500,502,503,504]):
            soak_seen.add(identity);soak.append(r)
    reliability={}
    for kind in ['asr','tts','tts_stream','tts_ws']:
        records=[r for r in all_records if r['log']=='results/attempts.jsonl' and r['kind']==kind]
        reliability[kind]=dict(attempts=len(records),failed_attempts=sum(not r['success'] for r in records))
    summary=dict(request_records=len(all_records),stream_timelines_checked=len(stream_rows),
                 v3_streams_with_stalls=sum(r['model']=='timbre-v3.0' and r['stalls']>0 for r in stream_rows),
                 v25_streams_without_stalls=sum(r['model']=='timbre-v2.5' and r['stalls']==0 for r in stream_rows),
                 observed_window_utc=[min(timestamps),max(timestamps)],region='not recorded',
                 concurrency=capacity,soak=dict(requests=len(soak),successes=sum(r['success'] for r in soak)),baseline_reliability=reliability,
                 request_id_note='client IDs retained; server IDs only where historically logged',
                 backoff_policy='REST maximum four attempts; waits 1, 2, 4 seconds between attempts on 429/500/502/503/504 or network errors',
                 missing_historical_fields='ASR complete response headers and server request IDs were not retained for all historical requests; no values invented')
    (out/'diagnostic_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    return summary


if __name__=='__main__':
    destination=P/'results/reproduced';destination.mkdir(parents=True,exist_ok=True)
    print(json.dumps(audit(destination),indent=2))
