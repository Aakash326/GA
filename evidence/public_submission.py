"""Public-audio ASR benchmark and human-only TTS reporting profile.

Original dataset reference text is used for ASR; assistant-adjudicated reference
variants and model-only TTS assessments are excluded from headline results.
"""
from array import array
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import wave

from evaluation_metrics import corpus,score
from run_evaluation import PROJECT,read,selected,load,logs,latest,input_status,write_csv,tts_evaluation


def asr_public():
    manifest={'baseline':[m for m in selected('data/asr_manifest.csv') if not m['clip_id'].startswith('CALL-')],
              'followup':selected('data/next/asr_next_manifest.csv'),
              'public24':selected('data/next/asr_dataset_replacement.csv')}
    base={r['clip_id']:r for r in read('results/asr_results.csv')}
    attempts=logs('results/next/attempts.jsonl');rows=[]
    for cohort,group in manifest.items():
        for m in group:
            cid=m['clip_id'];integrity=input_status(m)
            if integrity!='sha256_verified':raise ValueError('Submission benchmark requires redistributed audio')
            no_speech=str(m.get('is_no_speech','')).lower()=='true'
            if cohort=='baseline':
                saved=base[cid];response=load(saved['raw_response_path']);hyp=response['transcript']
                reference='' if no_speech else m['source_or_prompt']
                model=m['model'];settings=dict(model=model,format=m['output_mode'],language_code=m['language'])
                raw_path=saved['raw_response_path'];latency=float(saved['latency_ms'])
                retry=float(saved['retry_inclusive_ms']);attempt=int(saved['attempt'])
            else:
                r=latest(attempts,'asr',cid,'run1' if cohort=='followup' else 'public_dataset_v1')
                response=load(r['raw_path']);hyp=response['transcript'];reference=m['reference_transcript']
                settings=r['settings'];model=settings['model'];raw_path=r['raw_path'];latency=float(r['latency_ms'])
                retry=r.get('retry_inclusive_ms','');attempt=r.get('attempt',1)
            if not reference and not no_speech:raise ValueError('Missing original dataset transcript')
            norm=score(reference,hyp);raw=score(reference,hyp,raw=True)
            rows.append(dict(clip_id=cid,cohort=cohort,language=m['language'],primary_language=m['language'].split(',')[0],
                             category=m['category'],speaker_id=m['speaker_id'],source_id=m.get('source_id',cid),
                             parent_clip_id=m.get('source_id','') if m.get('source_id','')!=cid else '',
                             source_dataset=m['source_dataset'],source_ref=m['source_ref'],
                             reference_source='original_dataset_text' if not no_speech else 'no_speech_control',
                             reference=reference,hypothesis=hyp,model=model,request_settings=json.dumps(settings,ensure_ascii=False),
                             input_path=m['input_path'],input_sha256=m['input_sha256'],input_integrity=integrity,
                             raw_response_path=raw_path,api_status='saved_success',latency_ms=latency,retry_inclusive_ms=retry,attempt=attempt,
                             is_no_speech=no_speech,scoring_eligible=True,
                             duration_s=float(m['duration_s']),sample_rate_hz=int(m['sample_rate_hz']),
                             raw_word_edits=raw['word_edits'],raw_ref_word_count=raw['ref_word_count'],raw_wer=raw['wer'],**norm))
    summary={}
    for cohort in manifest:
        group=[r for r in rows if r['cohort']==cohort];speech=[r for r in group if r['ref_word_count']]
        by_language={}
        for language in sorted({r['primary_language'] for r in speech}):
            by_language[language]=corpus([r for r in speech if r['primary_language']==language])
        by_category={category:corpus([r for r in speech if r['category']==category]) for category in sorted({r['category'] for r in speech})}
        summary[cohort]=dict(corpus(group),selected_clips=len(group),no_speech_controls=sum(r['is_no_speech'] for r in group),
                             no_speech_false_transcriptions=sum(bool(r['false_transcription']) for r in group if r['is_no_speech']),
                             raw_wer=sum(r['raw_word_edits'] for r in speech)/sum(r['raw_ref_word_count'] for r in speech),
                             by_language=by_language,by_category=by_category,
                             latency_ms_median=statistics.median(r['latency_ms'] for r in speech))
    overlap=[]
    for a,b in [('baseline','followup'),('baseline','public24'),('followup','public24')]:
        counts={k:len(({r[k] for r in manifest[a]}-{''})&({r[k] for r in manifest[b]}-{''})) for k in ['clip_id','input_sha256','source_ref','speaker_id']}
        if any(counts[k] for k in ['clip_id','input_sha256','source_ref']):raise ValueError('Duplicate submission input')
        overlap.append(dict(cohort_a=a,cohort_b=b,**counts))
    # Frozen edit totals independently traced to the released source-reference rows.
    expected={'baseline':(226,221,309,1630),'followup':(120,120,186,881),'public24':(24,24,48,249)}
    for name,(n,s,e,w) in expected.items():
        r=summary[name]
        if (r['selected_clips'],r['speech_clips'],r['word_edits'],r['reference_words'])!=(n,s,e,w):
            raise ValueError('Published source-reference denominator mismatch: '+name)
    return rows,summary,overlap


def tts_human():
    all_rows,_=tts_evaluation();human=[r for r in all_rows if r['assessor']=='human']
    summaries=[]
    for cohort in ['baseline','next']:
        group=[r for r in human if r['cohort']==cohort]
        summaries.append(dict(cohort=cohort,human_scored_prompts=len({r['case_id'] for r in group}),
                              human_scored_targets=len(group),correct_targets=sum(r['strict_correct'] for r in group),
                              wrong_targets=sum(r['result']=='wrong' for r in group),ambiguous_targets=sum(r['result']=='ambiguous' for r in group),
                              strict_accuracy=sum(r['strict_correct'] for r in group)/len(group),
                              critical_targets=sum(r['critical'] for r in group),critical_correct=sum(r['critical'] and r['strict_correct'] for r in group)))
    complete=[]
    for cid in sorted({r['case_id'] for r in all_rows if r['cohort']=='next'}):
        g=[r for r in all_rows if r['case_id']==cid]
        if all(r['assessor']=='human' for r in g):
            complete.append(dict(case_id=cid,pair_id=g[0]['pair_id'],form=g[0]['form'],correct=all(r['strict_correct'] for r in g)))
    pairs=[]
    for pair_id in sorted({r['pair_id'] for r in complete}):
        g={r['form']:r for r in complete if r['pair_id']==pair_id}
        if 'raw' not in g or 'rewritten' not in g:continue
        a,b=g['raw']['correct'],g['rewritten']['correct']
        pairs.append(dict(pair_id=pair_id,raw_case_id=g['raw']['case_id'],rewritten_case_id=g['rewritten']['case_id'],raw_correct=a,rewritten_correct=b,
                          outcome='fixed' if b and not a else 'regressed' if a and not b else 'both_correct' if a else 'both_failed'))
    return human,summaries,pairs


def naturalness_human():
    candidates=defaultdict(list)
    for r in read('results/listening_ratings.csv'):
        if r.get('naturalness_1to5') and r.get('prosody_1to5'):
            key=(r['case_id'],r['listener_id'],r['rated_at'])
            candidates[key].append(r)
    ratings=[]
    for (cid,listener,rated_at),group in candidates.items():
        values={(int(r['naturalness_1to5']),int(r['prosody_1to5'])) for r in group}
        if len(values)!=1:raise ValueError('Conflicting repeated clip-level human ratings')
        n,p=next(iter(values))
        if not (1<=n<=5 and 1<=p<=5):raise ValueError('Human quality rating outside 1–5')
        r=group[0]
        ratings.append(dict(case_id=cid,listener_id=listener,rated_at_utc=rated_at,naturalness_1to5=n,prosody_1to5=p,
                            repeated_target_rows=len(group),source='results/listening_ratings.csv',
                            blind_before_reveal=r.get('blind_before_reveal') or 'not_recorded',
                            listener_language_qualification=r.get('listener_languages') or 'not_recorded'))
    clip_groups=defaultdict(list)
    for r in ratings:clip_groups[r['case_id']].append(r)
    natural=[statistics.mean(r['naturalness_1to5'] for r in g) for g in clip_groups.values()]
    prosody=[statistics.mean(r['prosody_1to5'] for r in g) for g in clip_groups.values()]
    summary=dict(assessment_scope='existing single-listener descriptive ratings; language qualification not recorded',
                 unique_clips=len(clip_groups),listeners=len({r['listener_id'] for r in ratings}),ratings=len(ratings),
                 source_target_rows=sum(r['repeated_target_rows'] for r in ratings),
                 naturalness_mean=statistics.mean(natural),naturalness_median=statistics.median(natural),
                 prosody_mean=statistics.mean(prosody),prosody_median=statistics.median(prosody),
                 limitations='Four selected clips, one listener, non-blind/not-recorded reveal order; not population MOS or broad language validation')
    return ratings,summary


def paired_experiments(asr_rows,out):
    base={r['clip_id']:r for r in asr_rows if r['cohort']=='baseline'}
    attempts=logs('results/next/attempts.jsonl');by_tag=defaultdict(dict)
    for r in attempts:
        if r.get('ok') and r.get('kind') in ['asr','stt_stream'] and r.get('case_id') in base:
            by_tag[r.get('run_tag','')][r['case_id']]=r
    comparisons={};exports=[]
    for tag in ['keyterms','v25','ws']:
        before=[];after=[];terms=[]
        for cid,r in by_tag[tag].items():
            b=base[cid]
            response=r if r.get('kind')=='stt_stream' and 'transcript' in r else load(r.get('raw_path') or f'results/next/raw/stt_stream/{cid}/{tag}.json')
            prediction=response.get('transcript','')
            before.append(score(b['reference'],b['hypothesis']));after.append(score(b['reference'],prediction))
            terms.append(dict(clip_id=cid,experiment=tag,reference=b['reference'],baseline_hypothesis=b['hypothesis'],
                              comparison_hypothesis=prediction,request_settings=json.dumps(r['settings'],ensure_ascii=False) if 'settings' in r else '',
                              baseline_word_edits=before[-1]['word_edits'],comparison_word_edits=after[-1]['word_edits'],
                              ref_word_count=before[-1]['ref_word_count']))
        if before:
            comparisons[tag]=dict(clips=len(before),before=corpus(before),after=corpus(after))
            exports.extend(terms)
    write_csv(out/'paired_model_keyterm_streaming.csv',exports)
    pairs=[];by_condition=defaultdict(lambda:([],[]))
    for p in read('results/asr_paired_deltas.csv'):
        if p['clip_id'] not in base or p['source'] not in base:continue
        a,b=base[p['source']],base[p['clip_id']]
        before,after=by_condition[p['condition']];before.append(a);after.append(b)
        pairs.append(dict(condition=p['condition'],clip_id=p['clip_id'],parent_clip_id=p['source'],
                          before_word_edits=a['word_edits'],after_word_edits=b['word_edits'],
                          before_ref_words=a['ref_word_count'],after_ref_words=b['ref_word_count']))
    comparisons['acoustic_conditions']={c:dict(pairs=len(a),before=corpus(a),after=corpus(b),delta_wer_pp=(corpus(b)['wer']-corpus(a)['wer'])*100) for c,(a,b) in by_condition.items()}
    write_csv(out/'paired_acoustic_conditions.csv',pairs)
    return comparisons


def audio_quality(out):
    """Objective diagnostics; silence and near-full-scale samples are not naturalness scores."""
    import numpy as np
    rows=[]
    for manifest,folder in [('data/tts_cases.csv','results/tts_audio'),('data/next/tts_next_cases.csv','results/next/audio')]:
        for m in selected(manifest):
            path=PROJECT/folder/(m['case_id']+'.wav')
            with wave.open(str(path),'rb') as wav:
                rate=wav.getframerate();advertised_count=wav.getnframes();channels=wav.getnchannels();width=wav.getsampwidth()
                if channels!=1 or width!=2:raise ValueError('Expected PCM16 mono quality input')
                # REST responses can carry streaming/unknown-length RIFF placeholders.
                # Bound allocations by actual file bytes, then count decoded samples.
                pcm=array('h',wav.readframes(path.stat().st_size//(width*channels)))
                count=len(pcm)//channels
            if sys.byteorder!='little':pcm.byteswap()
            if not pcm:raise ValueError('Empty generated audio')
            size=max(1,round(rate*.02));samples=np.asarray(pcm,dtype=np.float64)
            frames=len(pcm)//size;blocks=samples[:frames*size].reshape(frames,size)
            rms=np.sqrt(np.mean(blocks*blocks,axis=1))/32768
            if len(pcm)%size:rms=np.append(rms,np.sqrt(np.mean(samples[frames*size:]**2))/32768)
            silence=(rms<10**(-50/20)).tolist()
            spans=[];start=None
            for i,silent in enumerate(silence+[False]):
                if silent and start is None:start=i
                if not silent and start is not None:spans.append((start,i));start=None
            internal=[(b-a)*.02 for a,b in spans if a>0 and b<len(silence)]
            rows.append(dict(case_id=m['case_id'],language=m['language'],model=m['model'],voice=m['voice'],
                             audio_path=path.relative_to(PROJECT).as_posix(),audio_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             decoded_duration_s=count/rate,sample_rate_hz=rate,channels=channels,
                             advertised_header_frames=advertised_count,decoded_frames=count,
                             header_length_matches_decoded=advertised_count==count,
                             peak=float(np.max(np.abs(samples)))/32768,near_full_scale_samples=int(np.count_nonzero(np.abs(samples)>=32760)),
                             sample_count=len(pcm),longest_internal_low_energy_s=max(internal,default=0),
                             low_energy_threshold_dbfs=-50,analysis_frame_ms=20))
    write_csv(out/'tts_audio_quality.csv',rows)
    return dict(clips=len(rows),decoded_nonempty=len(rows),
                clips_with_near_full_scale_samples=sum(r['near_full_scale_samples']>0 for r in rows),
                clips_with_placeholder_header_lengths=sum(not r['header_length_matches_decoded'] for r in rows),
                clips_with_internal_low_energy_over_500ms=sum(r['longest_internal_low_energy_s']>.5 for r in rows),
                max_internal_low_energy_s=max(r['longest_internal_low_energy_s'] for r in rows),
                note='PCM integrity/level/pause diagnostics, not perceptual naturalness; low energy can be an intentional pause')


def run(out,part='all',reports=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    summary=dict(profile='public_submission',new_api_calls=0,
                 asr_reference_basis='original dataset text',
                 tts_score_basis='explicit human marks only')
    if part in ['all','asr']:
        rows,scores,overlap=asr_public();write_csv(out/'asr_results.csv',rows);write_csv(out/'cohort_overlap.csv',overlap)
        asr_inputs=rows
        write_csv(out/'evidence_manifest.csv',[{k:r[k] for k in ['clip_id','cohort','language','speaker_id','source_dataset','source_ref','parent_clip_id','reference_source','input_path','input_sha256','input_integrity','scoring_eligible']} for r in rows])
        summary.update(asr=scores,cohort_overlap=overlap)
        summary['paired_experiments']=paired_experiments(rows,out)
    if part in ['all','tts']:
        rows,scores,pairs=tts_human();write_csv(out/'tts_results.csv',rows);write_csv(out/'tts_provenance.csv',scores);write_csv(out/'tts_human_rewrite_pairs.csv',pairs)
        ratings,quality=naturalness_human();write_csv(out/'tts_human_quality_ratings.csv',ratings)
        summary.update(tts_human=scores,tts_human_rewrite_pairs=dict(Counter(r['outcome'] for r in pairs)),naturalness=quality,
                       tts_audio_quality=audio_quality(out))
    if part=='all':
        from scripts.reconcile_measurements import reconcile
        summary['latency']=reconcile(asr_inputs,out)
        from scripts.validate_playback import validate
        summary['playback_validation']=validate(PROJECT/'results/playback_validation')
        from scripts.audit_evidence import audit
        summary['request_diagnostics']=audit(out)
    if part in ['all','tts'] and (PROJECT/'data/timbre_followup_cases.csv').exists():
        from scripts.analyze_timbre_followup import analyze
        summary['timbre_followup']=analyze(PROJECT)
    if part in ['all','tts'] and (PROJECT/'results/report4/protocol.json').exists():
        from scripts.analyze_report4 import analyze as report4_analyze
        from scripts.analyze_report4_heldout import analyze as heldout_analyze
        summary['report4']=report4_analyze(PROJECT)
        summary['report4_heldout']=heldout_analyze(PROJECT)
        from scripts.build_timbre_comparison import build as build_comparison
        build_comparison(PROJECT)
    if part in ['all','tts'] and (PROJECT/'results/report4/protocol.json').exists():
        from scripts.reconcile_rest_sets import reconcile as reconcile_rest_sets
        summary['rest_count_reconciliation']=reconcile_rest_sets(PROJECT,out)
    summary['headline_reconciliation']='passed'
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    if reports:
        env={**os.environ,'GNANI_EVALUATION_SUMMARY':str(out/'summary.json')}
        for script,name in [('build_report.py','report.pdf'),('build_next_report.py','next_stages_report.pdf')]:
            subprocess.run([sys.executable,str(PROJECT/'scripts'/script)],check=True,cwd=PROJECT,env=env)
            if (PROJECT/name).resolve()!=(out/name).resolve():shutil.copy2(PROJECT/name,out/name)
    displayed=out.relative_to(PROJECT) if out.is_relative_to(PROJECT) else out.name
    print(f'Public-dataset ASR / human-reviewed TTS {part} replay passed: {displayed}')
    return summary
