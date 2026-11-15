"""Optional live listening screen of reconstructed playback and planted controls."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'scripts'))
import timbre_followup as t
from analyze_timbre_followup import read,write


def run(live=False):
    from dotenv import dotenv_values
    model=dotenv_values(P/'.env').get('GEMINI_JUDGE_MODEL') or 'gemini-3.8-flash'
    out=P/'results/timbre_followup';tasks=[]
    for row in read(out/'stream_playback.csv'):
        tasks.append(dict(id=row['case_id']+'-playback',path=out/row['immediate_path'],
                          kind='network_arrival_reconstruction',known_gap=row['starvation_s'],source_case_id=row['case_id']))
    source=out/'listen/NF-R-3-short-1.wav'
    if source.exists():
        x,rate=sf.read(source,dtype='float32');folder=out/'judge_controls';folder.mkdir(exist_ok=True)
        # Planted positive control: 80-ms tone, 900-ms zeros, then untouched speech.
        tone=.15*np.sin(2*np.pi*800*np.arange(round(.08*rate))/rate)
        positive=folder/'planted_tone_then_gap.wav';sf.write(positive,np.concatenate([tone,np.zeros(round(.9*rate)),x]),rate,subtype='PCM_16')
        negative=folder/'unchanged_speech.wav';sf.write(negative,x,rate,subtype='PCM_16')
        tasks.extend([dict(id='PLANTED-positive',path=positive,kind='synthetic_positive_control',known_gap=.9,source_case_id='NF-R-3-short-1'),
                      dict(id='PLANTED-negative',path=negative,kind='unchanged_negative_control',known_gap=0,source_case_id='NF-R-3-short-1')])
    results=[]
    for task in tasks:
        result=t.judge_request('playback',task['id'],[task['path']],t.BLIND_PROMPT,model,live)
        if result:
            results.append(dict(id=task['id'],kind=task['kind'],source_case_id=task['source_case_id'],known_inserted_gap_s=task['known_gap'],
                                audio_path=task['path'].relative_to(P).as_posix(),audio_sha256=hashlib.sha256(task['path'].read_bytes()).hexdigest(),
                                **result['reply'],judge_model=result['model'],assessor='audio_model_provisional'))
            print('Playback/control judgment',task['id'],result['reply'].get('initial_sound_then_unexpected_silence'),flush=True)
    write(out/'playback_judge_checks.csv',results)
    return results


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');run(ap.parse_args().live)
