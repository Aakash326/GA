"""Rebuild published latency/RTF from attempt logs, real PCM lengths and run IDs."""
import hashlib
import statistics
import wave
from collections import defaultdict
from pathlib import Path
import sys

P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from run_evaluation import read,logs,latest,write_csv


def reconcile(asr_rows,out):
    attempts=logs('results/attempts.jsonl');base=[r for r in asr_rows if r['cohort']=='baseline']
    asr_trace=[]
    for r in base:
        hits=[a for a in attempts if a.get('kind')=='asr' and a.get('case_id')==r['clip_id'] and a.get('ok') and a.get('raw_path')==r['raw_response_path']]
        if not hits or abs(float(hits[-1]['latency_ms'])-r['latency_ms'])>1e-8:raise ValueError('ASR latency trace mismatch')
        a=hits[-1]
        asr_trace.append(dict(clip_id=r['clip_id'],is_no_speech=r['is_no_speech'],latency_ms=r['latency_ms'],
                              request_id=a.get('request_id',''),run_tag=a['run_tag'],raw_path=a['raw_path'],input_sha256=r['input_sha256']))
    tts_trace=[]
    for r in read('results/tts_results.csv'):
        a=latest(attempts,'tts',r['case_id'])
        if abs(a['latency_ms']-float(r['response_latency_ms']))>1e-8:raise ValueError('TTS latency differs from saved attempt')
        if a['settings']['model']!=r['model'] or a['settings']['voice']!=r['voice']:raise ValueError('TTS model/voice identity mismatch')
        path=P/r['audio_output_path']
        with wave.open(str(path),'rb') as w:
            rate=w.getframerate();channels=w.getnchannels();width=w.getsampwidth()
            pcm=w.readframes(path.stat().st_size//(channels*width))
        if len(pcm)%(channels*width):raise ValueError('Incomplete audio sample')
        frames=len(pcm)//(channels*width);duration=frames/rate
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=r['audio_sha256'] or duration<=0:raise ValueError('TTS decoded audio/hash mismatch')
        if abs(duration-float(r['audio_duration_s']))>.001:raise ValueError('TTS duration differs from saved decoded duration')
        rtf=a['latency_ms']/1000/duration
        if abs(rtf-float(r['rtf']))>.000051:raise ValueError('TTS RTF differs from latency/PCM duration')
        tts_trace.append(dict(case_id=r['case_id'],model=r['model'],voice=r['voice'],request_id=a.get('request_id',''),run_tag=a['run_tag'],
                              latency_ms=a['latency_ms'],retry_inclusive_ms=a.get('retry_inclusive_ms'),decoded_frames=frames,
                              sample_rate_hz=rate,decoded_duration_s=duration,rtf=rtf,audio_path=r['audio_output_path'],audio_sha256=digest))
    connection_trace=[];groups=defaultdict(list)
    for r in read('results/tts_ws_vs_sse.csv'):
        if r['case_id']!='T31':continue
        kind='tts_ws' if r['transport']=='WebSocket' else 'tts_stream'
        a=latest(attempts,kind,r['case_id'],r['run'])
        if a['settings']['model']!='timbre-'+r['model'] or a['settings']['voice']!=r['voice']:raise ValueError('Connection model/voice identity mismatch')
        connect=float(a.get('connect_ms') or 0) if r['connection']=='cold' else 0.
        smooth=float(a['stall_free_start_ms']);total=smooth+connect
        if abs(total-float(r['smooth_total_ms']))>.11:raise ValueError('Connection timer reconciliation failed')
        key=f'{r["model"]}|{r["transport"]}|{r["connection"]}'
        row=dict(case_id=r['case_id'],model=r['model'],voice=r['voice'],transport=r['transport'],connection=r['connection'],
                 run_tag=r['run'],request_id=a.get('request_id',''),connect_ms=connect,smooth_start_ms=smooth,smooth_total_ms=total,
                 timeline_path=a.get('timeline_path',''))
        groups[key].append(row);connection_trace.append(row)
    final_trace=[];seen={};baseline_ids={r['clip_id'] for r in base}
    for r in logs('results/next/attempts.jsonl'):
        if r.get('kind')=='stt_stream' and r.get('run_tag')=='ws' and r.get('ok') and r.get('case_id') in baseline_ids:
            seen[r['case_id']]=r
    for cid,r in seen.items():
        if r.get('last_final_after_speech_ms') is not None:
            final_trace.append(dict(clip_id=cid,final_after_audio_ms=r['last_final_after_speech_ms'],run_tag=r['run_tag'],
                                    raw_path=r.get('raw_path') or f'results/next/raw/stt_stream/{cid}/ws.json'))
    write_csv(out/'asr_latency_trace.csv',asr_trace);write_csv(out/'tts_latency_rtf_trace.csv',tts_trace)
    write_csv(out/'tts_connection_latency_trace.csv',connection_trace);write_csv(out/'asr_stream_latency_trace.csv',final_trace)
    result=dict(asr_rest_speech_n=sum(not r['is_no_speech'] for r in asr_trace),
                asr_rest_latency_ms_median=statistics.median(r['latency_ms'] for r in asr_trace if not r['is_no_speech']),
                tts_rest_prompts=len(tts_trace),tts_rest_latency_ms_median=statistics.median(r['latency_ms'] for r in tts_trace),
                tts_rest_rtf_median=statistics.median(r['rtf'] for r in tts_trace),
                connections={key:dict(runs=len(g),smooth_total_ms=statistics.median(r['smooth_total_ms'] for r in g)) for key,g in groups.items()},
                asr_stream_clips=len(final_trace),asr_final_after_audio_ms_median=statistics.median(r['final_after_audio_ms'] for r in final_trace),
                status='all source timers, PCM durations, hashes and run IDs reconciled')
    if round(result['asr_rest_latency_ms_median'])!=192 or round(result['tts_rest_latency_ms_median']/1000,2)!=1.49 or round(result['tts_rest_rtf_median'],2)!=.37:
        raise ValueError('Published latency/RTF rounding mismatch')
    if result['asr_stream_clips']!=18:raise ValueError('ASR stream timer cohort must match the 18 paired benchmark inputs')
    return result
