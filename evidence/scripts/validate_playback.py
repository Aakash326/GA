"""Independent sample-accurate playback reconstruction from saved chunk events.

Validates byte counts against decoded PCM WAVs and renders audible underruns.
No API requests or sound-device assumptions are involved.
"""
import hashlib
import html
import json
from pathlib import Path
import sys
import wave

P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from run_evaluation import logs,load,write_csv


def schedule(arrivals, lengths, rate, start=None, tolerance_ms=1):
    """Integer-sample scheduler; returns starts, gaps and earliest no-underrun start."""
    if len(arrivals)!=len(lengths) or not arrivals:raise ValueError('Invalid chunk sequence')
    if any(n<=0 for n in lengths) or any(b<a for a,b in zip(arrivals,arrivals[1:])):raise ValueError('Invalid chunk ordering')
    preceding=0;earliest=0
    for arrival,length in zip(arrivals,lengths):
        earliest=max(earliest,arrival-preceding);preceding+=length
    cursor=arrivals[0] if start is None else start
    if tolerance_ms<0:raise ValueError('Negative scheduling tolerance')
    starts=[];gaps=[];all_gaps=[]
    for i,(arrival,length) in enumerate(zip(arrivals,lengths)):
        wait=max(0,arrival-cursor)
        if i and wait>0:all_gaps.append((cursor,wait))
        if i and wait>rate*tolerance_ms/1000:gaps.append((cursor,wait))
        cursor=max(cursor,arrival);starts.append(cursor);cursor+=length
    return dict(starts=starts,gaps=gaps,all_gaps=all_gaps,earliest_start=earliest,end=cursor)


def buffer_sensitivity(chosen,out):
    rows=[]
    for r in chosen.values():
        chunks=load(r['timeline_path'])['chunks'];rate=r['settings']['audio_config']['sample_rate']
        lengths=[c['bytes']//2 for c in chunks];arrivals=[round(c['t_s']*rate) for c in chunks]
        for prebuffer in [0,50,100,200]:
            start=arrivals[0]+round(rate*prebuffer/1000)
            for tolerance in [1,10,20]:
                result=schedule(arrivals,lengths,rate,start=start,tolerance_ms=tolerance)
                stable_sample=max((position+gap for position,gap in result['all_gaps']),default=start)
                rows.append(dict(case_id=r['case_id'],run_tag=r['run_tag'],model=r['settings']['model'],
                                 sample_rate_hz=rate,initial_prebuffer_ms=prebuffer,tolerance_ms=tolerance,
                                 underflow_count=len(result['gaps']),
                                 total_starvation_ms=sum(gap for _,gap in result['all_gaps'])/rate*1000,
                                 counted_starvation_ms=sum(gap for _,gap in result['gaps'])/rate*1000,
                                 startup_delay_ms=start/rate*1000,
                                 stable_playback_from_dispatch_ms=stable_sample/rate*1000,
                                 stable_after_start_ms=(stable_sample-start)/rate*1000,
                                 interpretation='retrospective last-underrun end; not an online stability detector'))
    write_csv(out/'buffer_sensitivity.csv',rows)
    aggregates=[]
    for prebuffer in [0,50,100,200]:
        for tolerance in [1,10,20]:
            for model in ['timbre-v3.0','timbre-v2.5']:
                group=[r for r in rows if r['initial_prebuffer_ms']==prebuffer and r['tolerance_ms']==tolerance and r['model']==model]
                aggregates.append(dict(model=model,initial_prebuffer_ms=prebuffer,tolerance_ms=tolerance,
                                       streams=len(group),streams_with_underflows=sum(r['underflow_count']>0 for r in group),
                                       starvation_ms_min=min(r['total_starvation_ms'] for r in group),
                                       starvation_ms_max=max(r['total_starvation_ms'] for r in group)))
    write_csv(out/'buffer_sensitivity_summary.csv',aggregates)
    return dict(conditions=len(rows),initial_prebuffers_ms=[0,50,100,200],tolerances_ms=[1,10,20],
                v3_underflow_in_all_conditions=all(r['underflow_count']>0 for r in rows if r['model']=='timbre-v3.0'),
                v25_no_underflows_in_all_conditions=all(r['underflow_count']==0 for r in rows if r['model']=='timbre-v2.5'),
                aggregation=aggregates)


def render(path,pcm,lengths,starts,rate):
    output=bytearray();offset=0
    for length,start in zip(lengths,starts):
        current=len(output)//2
        if start<current:raise ValueError('Overlapping playback chunks')
        output.extend(bytes((start-current)*2));output.extend(pcm[offset*2:(offset+length)*2]);offset+=length
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate);wav.writeframes(output)


def validate(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    chosen={}
    for r in logs('results/next/attempts.jsonl'):
        if r.get('kind')=='tts_stream' and r.get('ok') and r.get('case_id','').startswith('N8-'):
            chosen[r['case_id'],r['run_tag']]=r
    rows=[];gap_rows=[];cards=[]
    for r in chosen.values():
        audio=P/r['audio_path'];timeline=P/r['timeline_path'];chunks=load(r['timeline_path'])['chunks']
        with wave.open(str(audio),'rb') as wav:
            rate=wav.getframerate();n=wav.getnframes();pcm=wav.readframes(n)
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2:raise ValueError('Expected mono PCM16')
        if rate!=r['settings']['audio_config']['sample_rate']:raise ValueError('Rate mismatch')
        if any(c['bytes']%2 for c in chunks):raise ValueError('Partial PCM samples')
        lengths=[c['bytes']//2 for c in chunks]
        if sum(lengths)!=n:raise ValueError('Chunk bytes do not match saved WAV: '+r['case_id'])
        for c,length in zip(chunks,lengths):
            if abs(c['dur_s']-length/rate)>.000051:raise ValueError('Chunk duration/bytes mismatch')
        arrivals=[round(c['t_s']*rate) for c in chunks]
        immediate=schedule(arrivals,lengths,rate)
        buffered=schedule(arrivals,lengths,rate,start=immediate['earliest_start'])
        if buffered['gaps']:raise ValueError('Earliest-start policy still underflows')
        if len(immediate['gaps'])!=r['stalls']:raise ValueError('Independent stall count differs')
        extra=(immediate['earliest_start']-arrivals[0])/rate*1000
        previous=r['stall_free_start_ms']-r['ttfa_ms']
        rounding_bound_ms=(len(chunks)*.00005+.0002)*1000
        if abs(extra-previous)>rounding_bound_ms:raise ValueError('Independent extra wait exceeds the stored-duration rounding bound')
        stem=(r['case_id']+'__'+r['run_tag']).replace('.','_')
        first=out/(stem+'__immediate.wav');smooth=out/(stem+'__delayed.wav')
        render(first,pcm,lengths,immediate['starts'],rate);render(smooth,pcm,lengths,buffered['starts'],rate)
        for index,(position,size) in enumerate(immediate['gaps'],1):
            gap_rows.append(dict(case_id=r['case_id'],run_tag=r['run_tag'],gap=index,start_sample=position,
                                 silence_samples=size,sample_rate_hz=rate,start_s=position/rate,duration_s=size/rate))
        rows.append(dict(case_id=r['case_id'],run_tag=r['run_tag'],model=r['settings']['model'],voice=r['settings']['voice'],
                         sample_rate_hz=rate,chunks=len(chunks),wav_frames=n,chunk_frames=sum(lengths),
                         input_audio_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),timeline_sha256=hashlib.sha256(timeline.read_bytes()).hexdigest(),
                         first_audio_ms=arrivals[0]/rate*1000,immediate_stalls=len(immediate['gaps']),
                         inserted_silence_s=sum(size/rate for _,size in immediate['gaps']),
                         extra_wait_ms=extra,delayed_stalls=len(buffered['gaps']),
                         previous_rounded_duration_extra_wait_ms=previous,rounding_correction_ms=extra-previous,
                         immediate_playback=first.name,delayed_playback=smooth.name,byte_duration_check='passed'))
        cards.append(f'<section><h2>{html.escape(r["case_id"])} / {html.escape(r["run_tag"])}</h2>'
                     f'<p>{len(immediate["gaps"])} underruns; {extra/1000:.3f} s retrospective extra wait.</p>'
                     f'<p>Start immediately (network gaps reconstructed):</p><audio controls preload="none" src="{first.name}"></audio>'
                     f'<p>Retrospective delayed start:</p><audio controls preload="none" src="{smooth.name}"></audio></section>')
    if len(rows)!=14:raise ValueError('Expected 14 N8 streams')
    write_csv(out/'playback_validation.csv',rows);write_csv(out/'playback_gaps.csv',gap_rows)
    v3=[r for r in rows if r['model']=='timbre-v3.0'];v25=[r for r in rows if r['model']=='timbre-v2.5']
    summary=dict(status='passed',streams=len(rows),byte_duration_checks_passed=len(rows),
                 v3_streams=len(v3),v3_with_stalls=sum(r['immediate_stalls']>0 for r in v3),
                 v25_streams=len(v25),v25_with_stalls=sum(r['immediate_stalls']>0 for r in v25),
                 all_delayed_streams_without_stalls=all(r['delayed_stalls']==0 for r in rows),
                 v3_extra_wait_ms_min=min(r['extra_wait_ms'] for r in v3),v3_extra_wait_ms_max=max(r['extra_wait_ms'] for r in v3),
                 max_absolute_rounding_correction_ms=max(abs(r['rounding_correction_ms']) for r in rows),
                 definition='Independent integer-sample reconstruction of saved network arrivals; not new live/device measurements; delayed policy uses future arrivals')
    summary['buffer_sensitivity']=buffer_sensitivity(chosen,out)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    sensitivity='<h2>Buffer and tolerance sensitivity</h2><p>Fixed startup prebuffers of 0, 50, 100 and 200 ms were tested with 1, 10 and 20 ms reporting tolerances (168 stream/condition rows). The tested v3.0 traces underrun in every condition; the two v2.5 controls do not. These controls do not establish general model superiority.</p><p><a href="buffer_sensitivity.csv">Per-stream startup, starvation and stability measurements</a> · <a href="buffer_sensitivity_summary.csv">Condition summary</a></p>'
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Playback benchmark validation</title><style>body{font:16px system-ui;max-width:900px;margin:30px auto}section{padding:15px;border-top:1px solid #ccc}</style><h1>Playback benchmark validation</h1><p>Saved audio and chunk arrival times reconstructed into WAV playback. Initial silence represents measured startup; later inserted silence represents buffer underruns. These are offline reconstructions, not new live or handset recordings. Delayed starts use future arrivals and are not a universal buffer recommendation.</p>'+sensitivity+''.join(cards),encoding='utf8')
    return summary


if __name__=='__main__':print(json.dumps(validate(P/'results/playback_validation'),indent=2))
