"""One offline entry point for ASR and TTS, using immutable saved API evidence.

python run_evaluation.py --mode replay --part all --output-dir results/reproduced
No API libraries are imported. Private historical rows can be replayed from
preserved edit counts in the distributable bundle; this limitation is exported.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from evaluation_metrics import corpus, score

PROJECT = Path(__file__).resolve().parent
VALID = {'correct', 'wrong', 'ambiguous'}


def read(name):
    with (PROJECT/name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def load(name):
    return json.loads((PROJECT/name).read_text(encoding='utf8'))


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def truth(value):
    return str(value).lower() == 'true'


def selected(name):
    return [r for r in read(name) if truth(r.get('selected', 'true'))]


def logs(name):
    return [json.loads(line) for line in (PROJECT/name).read_text(encoding='utf8').splitlines() if line.strip()]


def latest(rows, kind, cid, tag='run1'):
    hits = [r for r in rows if r.get('kind') == kind and r.get('case_id') == cid and r.get('run_tag') == tag and r.get('ok')]
    if not hits:
        raise ValueError(f'Missing successful saved response: {kind}/{cid}/{tag}')
    return hits[-1]


def input_status(row):
    path = PROJECT/row['input_path']
    if not path.is_file():
        if row.get('evidence_visibility') == 'private_counts_only':
            return 'private_audio_omitted'
        raise ValueError(f'Missing public audio: {row["clip_id"]}')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if row.get('input_sha256') and digest != row['input_sha256']:
        raise ValueError(f'Input hash mismatch: {row["clip_id"]}')
    return 'sha256_verified'


def group_score(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    return {k: corpus(v) for k, v in sorted(groups.items())}


def asr_evaluation():
    manifests = {'baseline': selected('data/asr_manifest.csv'),
                 'followup': selected('data/next/asr_next_manifest.csv'),
                 'public24': selected('data/next/asr_dataset_replacement.csv')}
    baseline = {r['clip_id']: r for r in read('results/asr_results.csv')}
    provenance = {r['clip_id']: r for r in read('results/next/asr_reference_provenance.csv')}
    audit = {r['clip_id']: r for r in read('results/verification/final_reference_audit.csv')}
    attempts = logs('results/next/attempts.jsonl')
    rows = []
    for cohort, manifest in manifests.items():
        for m in manifest:
            cid = m['clip_id']; check = input_status(m)
            private = m.get('evidence_visibility') == 'private_counts_only'
            if cohort == 'baseline':
                saved = baseline[cid]
                ref, hyp = saved['reference_transcript'], saved['hypothesis_raw']
                reference_assessor = 'human' if truth(m['human_reference_verified']) else 'automated_or_dataset_provisional'
                if cid.startswith('CALL-'):
                    reference_assessor = 'historical_automated_reference_not_itemwise_human_verified'
                settings = dict(model=m['model'], format=m['output_mode'], language_code=m['language'])
                trace = {k: saved.get(k, '') for k in ['latency_ms', 'retry_inclusive_ms', 'attempt', 'raw_response_path']}
                if not private:
                    raw = load(saved['raw_response_path'])
                    if raw.get('transcript') != hyp:
                        raise ValueError(f'Saved transcript differs from raw response: {cid}')
            else:
                res = latest(attempts, 'asr', cid, 'run1' if cohort == 'followup' else 'public_dataset_v1')
                raw = load(res['raw_path']); hyp = raw['transcript']
                ref = provenance[cid]['reference'] if cohort == 'followup' else audit[cid]['resolved_reference']
                reference_assessor = provenance[cid]['reference_assessor'] if cohort == 'followup' else 'automated_provisional'
                settings = res['settings']
                trace = {k: res.get(k, '') for k in ['latency_ms', 'retry_inclusive_ms', 'attempt', 'request_id', 'fingerprint']}
                trace['raw_response_path'] = res['raw_path']
                if cid in audit and audit[cid]['input_sha256'] != m['input_sha256']:
                    raise ValueError(f'Reference audit/input mismatch: {cid}')
            row = dict(clip_id=cid, cohort=cohort, language=m['language'], primary_language=m['language'].split(',')[0], category=m['category'],
                       speaker_id=m['speaker_id'], source_id=m.get('source_id', cid),
                       source_dataset=m['source_dataset'], source_ref=m['source_ref'],
                       parent_clip_id=m.get('source_id', '') if m.get('source_id', '') != cid else '',
                       reference_source=m.get('reference_origin') or m.get('reference_status', ''),
                       reference_assessor=reference_assessor, source_reference=m['reference_transcript'],
                       reference=ref, hypothesis=hyp, input_path=m['input_path'], input_sha256=m['input_sha256'],
                       duration_s=m['duration_s'], sample_rate_hz=m['sample_rate_hz'],
                       model=settings['model'], output_mode=settings.get('format', 'transcribe'),
                       request_settings=json.dumps(settings, ensure_ascii=False, sort_keys=True),
                       scoring_eligible=True, is_no_speech=truth(m.get('is_no_speech', False)),
                       input_integrity=check, evidence_visibility='private_counts_only' if private else 'text_and_audio', **trace)
            if private:
                for key in ['ref_word_count','word_edits','ref_char_count','char_edits','substitutions','deletions','insertions']:
                    row[key] = int(saved[key])
                for key in ['nospace_ref_chars','nospace_char_edits']:
                    row[key] = int(saved[key])
                row.update(wer=float(saved['wer']), cer=float(saved['cer']))
                row.update({k: int(saved[k]) for k in ['raw_word_edits','raw_ref_word_count']})
                row['raw_wer'] = float(saved['raw_wer'])
            else:
                row.update(score(ref, hyp))
                raw_score = score(ref, hyp, raw=True)
                row.update({f'raw_{k}': raw_score[k] for k in ['word_edits', 'ref_word_count', 'wer']})
                source_score = score(m['reference_transcript'], hyp)
                row.update(source_word_edits=source_score['word_edits'], source_ref_word_count=source_score['ref_word_count'])
                if cohort == 'baseline':
                    for key in ['word_edits','ref_word_count','char_edits','ref_char_count']:
                        if int(saved[key]) != row[key]:
                            raise ValueError(f'Baseline metric reconciliation failed: {cid}/{key}')
            rows.append(row)
    summary = {}
    for cohort in manifests:
        group = [r for r in rows if r['cohort'] == cohort]
        summary[cohort] = dict(corpus(group), selected_clips=len(group), no_speech_controls=sum(r['is_no_speech'] for r in group),
                               private_counts_only=sum(r['evidence_visibility']=='private_counts_only' for r in group),
                               by_language=group_score([r for r in group if r['ref_word_count']], 'primary_language' if cohort=='baseline' else 'language'), by_category=group_score(group, 'category'))
        spoken = [r for r in group if r['ref_word_count']]
        summary[cohort]['raw_wer'] = sum(r['raw_word_edits'] for r in spoken)/sum(r['raw_ref_word_count'] for r in spoken)
    overlaps = []
    for a, b in [('baseline','followup'),('baseline','public24'),('followup','public24')]:
        overlap = {k: len(({r[k] for r in manifests[a]}-{''}) & ({r[k] for r in manifests[b]}-{''}))
                   for k in ['clip_id','input_sha256','source_ref','speaker_id']}
        if any(overlap[k] for k in ['clip_id','input_sha256','source_ref']):
            raise ValueError(f'Unexpected ASR cohort overlap: {a}/{b}')
        overlaps.append(dict(cohort_a=a, cohort_b=b, **overlap))
    return rows, summary, overlaps


def human_marks():
    marks = {}
    for name, field in [('results/listening_ratings.csv','adjudicated_result'),
                        ('results/tts_mitigation_ratings.csv','adjudicated_result'),
                        ('data/listening/n1_tts_filled.csv','target_result')]:
        for r in read(name):
            if r[field] in VALID and not truth(r.get('cannot_judge', False)):
                marks[r['case_id'],r['target_id']] = (r[field], name)
    # This export is applied last for follow-up targets by the supporting notebook.
    for r in read('data/listening/tts_listening_filled.csv'):
        if r['case_id'].startswith('NT') and r['target_result'] in VALID and not truth(r.get('cannot_judge',False)):
            marks[r['case_id'],r['target_id']] = (r['target_result'],'data/listening/tts_listening_filled.csv')
    return marks


def tts_evaluation():
    audit = {(r['cohort'],r['case_id'],r['target_id']): r for r in read('results/verification/tts_llm_verification.csv')}
    human = human_marks()
    generations = {r['case_id']: r for r in read('results/tts_results.csv')}
    attempts = logs('results/next/attempts.jsonl')
    selection = {r['case_id']:r for r in read('results/verification/human_priority50_selection.csv')}
    n1 = {(r['case_id'],r['target_id']):r for r in read('data/listening/n1_tts_filled.csv')}
    saved_baseline = {(r['case_id'],r['target_id']):r for r in read('results/tts_scored_targets.csv')}
    saved_next = {(r['case_id'],r['target']):r for r in read('results/next/tts_adjudicated.csv')}
    rows = []
    for cohort, manifest in [('baseline','data/tts_cases.csv'),('next','data/next/tts_next_cases.csv')]:
        for m in selected(manifest):
            cid=m['case_id']
            gen=generations[cid] if cohort == 'baseline' else latest(attempts,'tts',cid)
            audio=gen.get('audio_output_path') or gen.get('audio_path') or f'results/next/audio/{cid}.wav'
            digest=hashlib.sha256((PROJECT/audio).read_bytes()).hexdigest()
            for target in json.loads(m['expected_targets_json']):
                tid=target['id'];key=(cid,tid);a=audit[cohort,cid,tid]
                if digest != a['input_sha256']:
                    raise ValueError(f'TTS assessment/audio mismatch: {cid}/{tid}')
                result, origin=human.get(key,(a['result'],'results/verification/tts_llm_verification.csv'))
                if result not in VALID:
                    raise ValueError(f'Unresolved final assessment: {cid}/{tid}')
                is_human=key in human
                previous=(saved_baseline if cohort=='baseline' else saved_next)[key]
                if result != previous['final_result' if cohort=='baseline' else 'result']:
                    raise ValueError(f'TTS result differs from supporting notebook: {cid}/{tid}')
                selected_mark=n1.get(key,{})
                rows.append(dict(cohort=cohort,case_id=cid,target_id=tid,language=m['language'],category=m['category'],
                                 model=m['model'],voice=m['voice'],input_text=m['input_text'],
                                 form=m.get('input_form','baseline'),pair_id=m.get('pair_id',''),
                                 target_definition=json.dumps(target,ensure_ascii=False),critical=truth(target.get('critical',False)),
                                 result=result,strict_correct=result=='correct',assessor='human' if is_human else 'automated_provisional',
                                 assessment_source=origin,automated_result=a['result'],audio_path=audio,audio_sha256=digest,
                                 selected_for_priority50=cid in selection,
                                 selection_reason=selection.get(cid,{}).get('selection_reason',''),
                                 priority50_human_mark=selected_mark.get('target_result','') if not truth(selected_mark.get('cannot_judge',False)) else '',
                                 response_latency_ms=gen.get('response_latency_ms',gen.get('latency_ms','')),
                                 retry_inclusive_ms=gen.get('retry_inclusive_ms',''),attempt=gen.get('attempt',''),
                                 audio_duration_s=gen.get('audio_duration_s',''),rtf=gen.get('rtf','')))
    provenance=[]
    for cohort in ['baseline','next']:
        g=[r for r in rows if r['cohort']==cohort]
        provenance.append(dict(cohort=cohort,prompts=len({r['case_id'] for r in g}),scored_targets=len(g),
                               human_scored_targets=sum(r['assessor']=='human' for r in g),
                               automated_scored_targets=sum(r['assessor']!='human' for r in g),
                               correct_targets=sum(r['strict_correct'] for r in g),
                               wrong_targets=sum(r['result']=='wrong' for r in g),ambiguous_targets=sum(r['result']=='ambiguous' for r in g),
                               selected_listening_targets=sum(r['selected_for_priority50'] for r in g),
                               selected_human_marked_targets=sum(r['priority50_human_mark'] in VALID for r in g),
                               selected_unmarked_targets=sum(r['selected_for_priority50'] and r['priority50_human_mark'] not in VALID for r in g),
                               by_assessor={a:dict(scored_targets=len(sg),correct_targets=sum(r['strict_correct'] for r in sg),
                                                  wrong_targets=sum(r['result']=='wrong' for r in sg),ambiguous_targets=sum(r['result']=='ambiguous' for r in sg))
                                            for a in ['human','automated_provisional'] if (sg:=[r for r in g if r['assessor']==a])}))
    return rows,provenance


def reconcile(asr,tts):
    main=load('results/summary_metrics.json');follow=load('results/next/summary_next.json')
    if asr:
        base=asr['baseline']
        for key,expected in [('wer',main['asr']['wer']),('raw_wer',main['asr']['raw_wer'])]:
            if abs(base[key]-expected)>0.000051:raise ValueError(f'Headline mismatch: baseline {key}')
        for language,g in base['by_language'].items():
            old=main['asr']['by_language'][language]
            if g['speech_clips']!=old['clips'] or abs(g['wer']-old['wer'])>0.000051:raise ValueError(f'Language headline mismatch: {language}')
        for entry in follow['n3']['by_language']:
            if abs(asr['followup']['by_language'][entry['language']]['wer']-entry['WER'])>0.000051:raise ValueError('Follow-up headline mismatch')
        if abs(asr['public24']['wer']-follow['n2_dataset']['wer'])>1e-10:raise ValueError('Public cohort headline mismatch')
    if tts:
        for r,total,correct in [(tts[0],main['tts']['targets'],main['tts']['hybrid_correct']),
                                (tts[1],sum(follow['n4']['targets'].values()),follow['n4']['targets']['correct'])]:
            if r['scored_targets']!=total or r['correct_targets']!=correct:raise ValueError('TTS headline mismatch')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['replay'],default='replay',help='Offline only; live collection uses scripts/run_batch.py --live with explicit case IDs.')
    parser.add_argument('--part',choices=['all','asr','tts'],default='all')
    parser.add_argument('--profile',choices=['submission','audit'],default='submission',help='Submission uses public audio, original source references and human-only TTS marks. Audit preserves the earlier mixed-assessor analysis.')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--reports',action='store_true',help='Also rebuild both two-page PDFs into the output directory.')
    args=parser.parse_args()
    if args.reports and args.part!='all':parser.error('--reports requires --part all so both report parts use the same reconciliation.')
    if args.reports and args.profile!='submission':parser.error('Published reports use --profile submission; --profile audit exports supporting data only.')
    if args.profile=='audit' and not (PROJECT/'results/summary_metrics.json').exists():parser.error('The restricted exploratory archive is not distributed; use the default submission profile.')
    out=(args.output_dir or PROJECT/('results/submission' if args.profile=='submission' else 'results/reproduced')).resolve()
    out.mkdir(parents=True,exist_ok=True)
    if args.profile=='submission':
        from public_submission import run
        run(out,args.part,args.reports)
        return
    summary={'mode':'replay','new_api_calls':0,'metric_policy':'custom Levenshtein; corpus-weighted; no-speech excluded from speech WER'}
    asr={};tts=[]
    if args.part in ['all','asr']:
        rows,asr,overlap=asr_evaluation();write_csv(out/'asr_results.csv',rows)
        write_csv(out/'cohort_overlap.csv',overlap)
        write_csv(out/'evidence_manifest.csv',[{k:r[k] for k in ['clip_id','cohort','language','speaker_id','source_dataset','source_ref','parent_clip_id','reference_source','reference_assessor','input_path','input_sha256','input_integrity','scoring_eligible','evidence_visibility']} for r in rows])
        summary['asr']=asr;summary['cohort_overlap']=overlap
    if args.part in ['all','tts']:
        rows,tts=tts_evaluation();write_csv(out/'tts_results.csv',rows)
        write_csv(out/'tts_provenance.csv',[{**r,'by_assessor':json.dumps(r['by_assessor'])} for r in tts])
        summary['tts_provenance']=tts
    reconcile(asr,tts)
    summary['headline_reconciliation']='passed'
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    if args.part=='all':
        from scripts.audit_evidence import audit as audit_diagnostics
        summary['diagnostics']=audit_diagnostics(out)
        (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    if args.reports:
        for script,name in [('build_report.py','report.pdf'),('build_next_report.py','next_stages_report.pdf')]:
            env={**os.environ,'GNANI_EVALUATION_SUMMARY':str(out/'summary.json')}
            subprocess.run([sys.executable,str(PROJECT/'scripts'/script)],check=True,cwd=PROJECT,env=env)
            if (PROJECT/name).resolve()!=(out/name).resolve():shutil.copy2(PROJECT/name,out/name)
    print(f'Offline {args.part} evaluation complete; headline reconciliation passed; outputs: {out}')


if __name__=='__main__':
    main()
