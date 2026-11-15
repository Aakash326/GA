"""Separate held-out source-reference ASR results and unscored human TTS study."""
import hashlib,html,json,random,re,sys,statistics
from collections import Counter
from pathlib import Path
import numpy as np
import soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'scripts'))
from analyze_report4 import read,write,dump,logs,merge,decode,sha
from evaluation_metrics import normalize,score,corpus


def targets_in(text,terms):
    normalized=normalize(text)
    return [term for term in terms if re.search(r'(?<!\w)'+re.escape(normalize(term))+r'(?!\w)',normalized)]


def analyze(project=None):
    project=Path(project or P);data=project/'data/report4';out=project/'results/report4_quality'
    if not (data/'frozen_policy.json').exists():return None
    out.mkdir(parents=True,exist_ok=True);policy=json.loads((data/'frozen_policy.json').read_text(encoding='utf8'));policy_hash=sha(data/'frozen_policy.json')
    records=merge(logs(out/'attempts.jsonl'));by_case={r['case_id']:r for r in records}
    asr=[];pairs=[]
    for row in read(data/'asr_heldout_manifest.csv'):
        if sha(project/row['input_path'])!=row['input_sha256'] or policy_hash!=row['frozen_vocabulary_sha256']:raise ValueError('Held-out evidence changed')
        results={}
        for condition in ['baseline','hinted']:
            a=by_case.get(row['clip_id']+'-'+condition)
            if not a or not a.get('ok'):continue
            body=json.loads((project/a['raw_path']).read_text(encoding='utf8'));hyp=body.get('transcript','');reference=row['reference_transcript']
            scoring=score(reference,hyp);terms=json.loads(row['target_terms_json']);present=targets_in(hyp,terms)
            inserted=[t for t in targets_in(hyp,policy['keyterms']) if normalize(t) not in {normalize(x) for x in targets_in(reference,policy['keyterms'])}]
            numeric_ref=re.findall(r'(?<!\w)-?\d+(?:[.:]\d+)?',normalize(reference));numeric_hyp=re.findall(r'(?<!\w)-?\d+(?:[.:]\d+)?',normalize(hyp))
            reference_negative=bool(re.search(r"\b(?:not|never|no|cannot|don t|can t)\b",normalize(reference)))
            hypothesis_negative=bool(re.search(r"\b(?:not|never|no|cannot|don t|can t)\b",normalize(hyp)))
            result=dict(clip_id=row['clip_id'],condition=condition,reference=reference,hypothesis=hyp,**scoring,
                        target_terms_json=row['target_terms_json'],target_terms_correct=len(present),target_terms_total=len(terms),
                        target_set_exact=len(present)==len(terms),numeric_string_sequence_match=numeric_ref==numeric_hyp,
                        negative_marker_match=reference_negative==hypothesis_negative,
                        critical_lexical_slots_correct=len(present)==len(terms) and numeric_ref==numeric_hyp and reference_negative==hypothesis_negative,
                        hinted_vocabulary_insertion_flags_json=json.dumps(inserted),hinted_vocabulary_insertion_flags=len(inserted),
                        request_id=a['request_id'],latency_ms=a['latency_ms'],input_path=row['input_path'],input_sha256=row['input_sha256'],
                        response_path=a['raw_path'],response_sha256=sha(project/a['raw_path']),policy_sha256=policy_hash,
                        source_dataset=row['source_dataset'],source_ref=row['source_ref'],source_locale=row.get('source_locale','en-IN'))
            asr.append(result);results[condition]=result
        if len(results)==2:
            before=results['baseline'];after=results['hinted']
            pairs.append(dict(clip_id=row['clip_id'],baseline_word_edits=before['word_edits'],hinted_word_edits=after['word_edits'],
                              delta_word_edits=after['word_edits']-before['word_edits'],baseline_wer=before['wer'],hinted_wer=after['wer'],
                              outcome='improved' if after['word_edits']<before['word_edits'] else 'regressed' if after['word_edits']>before['word_edits'] else 'unchanged',
                              baseline_target_exact=before['target_set_exact'],hinted_target_exact=after['target_set_exact'],
                              hinted_vocabulary_insertion_flags=after['hinted_vocabulary_insertion_flags']))
    write(out/'asr_heldout_keyterm_results.csv',asr);write(out/'asr_heldout_pairs.csv',pairs)
    asr_summary={}
    for condition in ['baseline','hinted']:
        group=[r for r in asr if r['condition']==condition]
        if group:asr_summary[condition]=dict(corpus(group),target_terms_correct=sum(r['target_terms_correct'] for r in group),
           target_terms_total=sum(r['target_terms_total'] for r in group),target_set_exact_clips=sum(r['target_set_exact'] for r in group),
           critical_lexical_slots_correct_clips=sum(r['critical_lexical_slots_correct'] for r in group),
           hinted_vocabulary_insertion_flags=sum(r['hinted_vocabulary_insertion_flags'] for r in group))
    manifests=read(data/'tts_quality_manifest.csv')+read(data/'tts_rewrite_manifest.csv');audio=[]
    for m in manifests:
        a=by_case.get(m['case_id'])
        if not a or not a.get('ok') or not a.get('audio_path'):continue
        stats,x=decode(project/a['audio_path']);dest=out/'listen'/(m['case_id']+'.wav');dest.parent.mkdir(exist_ok=True)
        if not dest.exists():sf.write(dest,x,stats['sample_rate'],subtype='PCM_16')
        audio.append(dict(**m,audio_path=dest.relative_to(project).as_posix(),audio_sha256=sha(dest),audio_duration_s=stats['audio_duration_s'],request_id=a['request_id']))
    write(out/'tts_audio_manifest.csv',audio)
    quality=[r for r in audio if r['case_id'].startswith('R4-Q')];rewrite=[r for r in audio if r['case_id'].startswith('R4-N')]
    # Opaque, condition-blinded audio names. A separate key is excluded from the listening page.
    shuffled=sorted(quality,key=lambda r:r['case_id']);random.Random(4104).shuffle(shuffled);key=[]
    for i,row in enumerate(shuffled,1):
        blind_id=f'Q{i:03d}';dest=out/'blind_audio'/(blind_id+'.wav');dest.parent.mkdir(exist_ok=True)
        if not dest.exists():dest.write_bytes((project/row['audio_path']).read_bytes())
        key.append(dict(blind_id=blind_id,case_id=row['case_id'],prompt_id=row['prompt_id'],model=row['model'],condition=row['condition'],
                        blind_audio_path=dest.relative_to(project).as_posix(),audio_sha256=sha(dest)))
    write(out/'tts_listening_key.csv',key)
    columns=['listener_id','blind_id','language_qualification','naturalness','intelligibility','pronunciation','prosody','expressiveness','heard','notes']
    template=out/'tts_listening_scores.csv'
    if not template.exists() and quality:
        write(template,[dict.fromkeys(columns,'')|dict(listener_id=listener,blind_id=r['blind_id']) for listener in ['L1','L2','L3'] for r in key])
    rewrite_sheet=out/'tts_rewrite_pairs.csv'
    if not rewrite_sheet.exists() and len(rewrite)==20:
        by_id={r['case_id']:r for r in rewrite};sheet=[]
        for pair_id in sorted(set(r['pair_id'] for r in rewrite)):
            a=by_id[pair_id+'-raw'];b=by_id[pair_id+'-rewrite']
            sheet.append(dict(pair_id=pair_id,category=a['category'],language=a['language'],model=a['model'],expected_meaning=a['expected_meaning'],
                              raw_case_id=a['case_id'],rewrite_case_id=b['case_id'],raw_audio_path=a['audio_path'],rewrite_audio_path=b['audio_path'],
                              listener_id='',raw_correct='',rewrite_correct='',outcome='',notes=''))
        write(rewrite_sheet,sheet)
    supplied=read(template);completed=[r for r in supplied if any(str(r.get(k,'' )).strip() for k in ['naturalness','intelligibility','pronunciation','prosody','expressiveness'])]
    scores=[];valid_ids={r['blind_id'] for r in key}
    for r in completed:
        if r['blind_id'] not in valid_ids or not r['listener_id'].strip() or not r['language_qualification'].strip():raise ValueError('Listening provenance incomplete')
        for field in ['naturalness','intelligibility','pronunciation','prosody','expressiveness']:
            if r.get(field,'').strip() and (not r[field].isdigit() or not 1<=int(r[field])<=5):raise ValueError('Listening score outside 1–5')
        scores.append(r)
    if len({(r['listener_id'],r['blind_id']) for r in scores})!=len(scores):raise ValueError('Duplicate listener/clip ratings')
    key_by_id={r['blind_id']:r for r in key};clip_scores=[]
    matched_ids={pid for pid in {r['prompt_id'] for r in quality} if {r['model'] for r in quality if r['prompt_id']==pid and r['condition']=='version_neutral'}=={'timbre-v3.0','timbre-v2.5'}}
    for blind_id in sorted(valid_ids):
        g=[r for r in scores if r['blind_id']==blind_id]
        if not g:continue
        k=key_by_id[blind_id];row=dict(blind_id=blind_id,case_id=k['case_id'],model=k['model'],condition=k['condition'],
                                     eligible_paired_comparison=k['condition']=='version_neutral' and k['prompt_id'] in matched_ids,
                                     listeners=len(g),listener_ids=';'.join(sorted(r['listener_id'] for r in g)))
        for metric in ['naturalness','intelligibility','pronunciation','prosody','expressiveness']:
            values=[int(r[metric]) for r in g if r.get(metric)]
            if values:row.update({metric+'_mean':statistics.mean(values),metric+'_median':statistics.median(values),metric+'_listener_range':max(values)-min(values)})
        clip_scores.append(row)
    write(out/'tts_listening_clip_scores.csv',clip_scores)
    condition_scores=[]
    for model,condition in sorted({(r['model'],r['condition']) for r in clip_scores}):
        g=[r for r in clip_scores if r['model']==model and r['condition']==condition and (r['eligible_paired_comparison'] or condition!='version_neutral')]
        if not g:continue
        row=dict(model=model,condition=condition,clips=len(g),interpretation='clip means first; separate condition; small human panel, not population MOS')
        for metric in ['naturalness','intelligibility','pronunciation','prosody','expressiveness']:
            values=[r[metric+'_mean'] for r in g if metric+'_mean' in r]
            if values:row.update({metric+'_mean':statistics.mean(values),metric+'_median':statistics.median(values)})
        condition_scores.append(row)
    write(out/'tts_listening_condition_scores.csv',condition_scores)
    rewrite_completed=[]
    for r in read(rewrite_sheet):
        if r.get('raw_correct') or r.get('rewrite_correct'):
            if r.get('raw_correct') not in ['true','false'] or r.get('rewrite_correct') not in ['true','false'] or not r.get('listener_id'):raise ValueError('Incomplete held-out rewrite marks')
            raw=r['raw_correct']=='true';rewritten=r['rewrite_correct']=='true'
            rewrite_completed.append(dict(pair_id=r['pair_id'],outcome='both_correct' if raw and rewritten else 'newly_broken' if raw else 'fixed' if rewritten else 'both_wrong'))
    matched=sum({r['model'] for r in quality if r['prompt_id']==pid and r['condition']=='version_neutral'}=={'timbre-v3.0','timbre-v2.5'} for pid in {r['prompt_id'] for r in quality})
    s=dict(new_api_calls_in_replay=0,asr_paired_clips=len(pairs),asr=asr_summary,paired_outcomes=dict(Counter(r['outcome'] for r in pairs)),
           quality_audio_available=len(quality),quality_audio_planned=len(read(data/'tts_quality_manifest.csv')),quality_unique_prompts=16,
           matched_neutral_prompt_pairs=matched,new_human_rating_rows=len(scores),rewrite_audio_available=len(rewrite),rewrite_pairs_scored=len(rewrite_completed),
           rewrite_outcomes=dict(Counter(r['outcome'] for r in rewrite_completed)),
           assessment_scope='Held-out banking source-reference ASR is separate from baseline; new TTS panel and rewrite scores require new human input.',
           critical_slots_definition='Frozen target-word set exactness plus numeric-string order and negative-marker presence; lexical diagnostics, not full semantic correctness.',
           source_limits='MInDS-14 en-US source speech with en-IN API hint; speaker identities unavailable; selected domain-term convenience sample; not Indian-accent population validation.',
           target_term_coverage=dict(Counter(t for r in read(data/'asr_heldout_manifest.csv') for t in json.loads(r['target_terms_json']))),
           policy_sha256=policy_hash)
    dump(out/'summary.json',s)
    build_listening_page(project,out,key,quality,rewrite)
    return s


def build_listening_page(project,out,key,quality,rewrite):
    by_id={r['case_id']:r for r in quality};items=[]
    for r in key:
        m=by_id[r['case_id']]
        items.append(dict(id=r['blind_id'],src='blind_audio/'+r['blind_id']+'.wav',prompt=re.sub(r'<[^>]+>\s*','',m['text']),intent=m['intent']))
    payload=json.dumps(items,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Blinded listening study</title><style>body{font:16px/1.6 system-ui;max-width:850px;margin:30px auto;padding:20px;color:#183247}select,input,textarea,button{font:inherit;padding:8px;margin:5px}label{display:block}audio{width:100%}fieldset{margin:15px 0}button{cursor:pointer}#reference{padding:12px;background:#eef4f7}small{color:#526679}</style><h1>Independent listening study</h1><p>Work independently as L1, L2 or L3. Model and condition names are hidden. Do not open the separate mapping key before submitting. First listen and write what you hear, then reveal the reference for pronunciation/expression ratings. Existing knowledge of the voices may reduce blinding.</p><p>1 = severe problems; 3 = noticeable issues but understandable; 5 = natural/appropriate/clear. Leave a score blank when unable to judge. This small panel is not an industry MOS benchmark.</p><label>Anonymous listener <select id="listener"><option>L1</option><option>L2</option><option>L3</option></select></label><label>Language familiarity <input id="language" placeholder="e.g. fluent English"></label><label>Clip in your randomized order <select id="clip"></select></label><audio id="audio" controls preload="none"></audio><label>What did you hear? <textarea id="heard" rows="3" style="width:100%"></textarea></label><button id="reveal">Save blind draft & reveal reference</button><p id="reference" hidden></p><fieldset id="ratings"><legend>Listening ratings</legend></fieldset><label>Notes / uncertainty <textarea id="notes" rows="2" style="width:100%"></textarea></label><button id="save">Save this clip locally</button><button id="export">Export this listener’s CSV</button><p id="status" role="status"></p><p><small>Scores are kept only in this browser until you export. Send the exported CSV for import; no network submission occurs. The response sheet in the repository remains blank until actual human scores are supplied.</small></p><script type="application/json" id="items">__DATA__</script><script>
const items=JSON.parse(document.getElementById('items').textContent),fields=['naturalness','intelligibility','pronunciation','prosody','expressiveness'];const $=x=>document.getElementById(x);let store={};try{store=JSON.parse(localStorage.getItem('gnani-report4-listening')||'{}')}catch(e){}
fields.forEach(f=>{let label=document.createElement('label');label.textContent=f+' ';let s=document.createElement('select');s.id=f;s.append(new Option('Unable to judge / blank',''));[1,2,3,4,5].forEach(n=>s.append(new Option(n,n)));label.append(s);$('ratings').append(label)});
function item(){return items.find(x=>x.id===$('clip').value)}function id(){return $('listener').value+'|'+$('clip').value}function save(){let r={listener_id:$('listener').value,blind_id:$('clip').value,language_qualification:$('language').value,heard:$('heard').value,notes:$('notes').value};fields.forEach(f=>r[f]=$(f).value);store[id()]=r;try{localStorage.setItem('gnani-report4-listening',JSON.stringify(store))}catch(e){}return r}
function show(){let r=store[id()]||{};$('audio').pause();$('audio').src=item().src;$('reference').hidden=true;$('heard').value=r.heard||'';$('notes').value=r.notes||'';if(r.language_qualification)$('language').value=r.language_qualification;fields.forEach(f=>$(f).value=r[f]||'')}
function order(){let seed=$('listener').value.charCodeAt(1)*4104;let sorted=[...items].sort((a,b)=>{const h=x=>[...x].reduce((v,c)=>(v*31+c.charCodeAt(0))>>>0,seed);return ((h(a.id)*1103515245)>>>0)-((h(b.id)*1103515245)>>>0)});$('clip').replaceChildren(...sorted.map(x=>new Option(x.id,x.id)));show()}
$('clip').onchange=show;$('listener').onchange=order;$('reveal').onclick=()=>{save();$('reference').textContent='Reference: '+item().prompt+' | Intended delivery: '+item().intent;$('reference').hidden=false};$('save').onclick=()=>{save();$('status').textContent='Saved locally. Export before sending your ratings.'};$('export').onclick=()=>{save();const columns=['listener_id','blind_id','language_qualification',...fields,'heard','notes'];const quote=v=>'"'+String(v||'').replaceAll('"','""')+'"';let rows=Object.values(store).filter(r=>r.listener_id===$('listener').value);let csv=[columns,...rows.map(r=>columns.map(c=>r[c]))].map(r=>r.map(quote).join(',')).join('\\r\\n');let u=URL.createObjectURL(new Blob(['\\ufeff'+csv],{type:'text/csv;charset=utf-8'}));let a=document.createElement('a');a.href=u;a.download='tts_listening_'+$('listener').value+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};order();
</script></html>'''.replace('__DATA__',payload)
    (out/'listening.html').write_text(page,encoding='utf8')
    cards=[];by_id={r['case_id']:r for r in rewrite}
    for pair in sorted(set(r['pair_id'] for r in rewrite)):
        a=by_id.get(pair+'-raw');b=by_id.get(pair+'-rewrite')
        if not a or not b:continue
        cards.append('<section><h2>'+pair+'</h2><p>Expected meaning: '+html.escape(a['expected_meaning'])+'</p>'+''.join('<p>'+html.escape(r['variant'])+': '+html.escape(r['text'])+'</p><audio controls preload="none" src="listen/'+r['case_id']+'.wav"></audio>' for r in [a,b])+'</section>')
    (out/'rewrites.html').write_text('<!doctype html><meta charset="utf-8"><title>Held-out text rewrites</title><style>body{font:16px system-ui;max-width:900px;margin:30px auto}section{padding:18px;border-top:1px solid #ccd}audio{width:100%}</style><h1>Ten held-out raw/rewrite pairs</h1><p>Rules were frozen before these outputs. English Kaveri / Timbre v2.5 only. New human correctness marks remain blank; record both correct, fixed, newly broken or both wrong in tts_rewrite_pairs.csv.</p>'+''.join(cards),encoding='utf8')


if __name__=='__main__':print(json.dumps(analyze(),ensure_ascii=False,indent=2))
