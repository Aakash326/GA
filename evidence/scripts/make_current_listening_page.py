"""Refresh N1 for all current baseline/next TTS targets. No API calls."""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'scripts'))
import make_tts_listening_page as ui

def read(name):
    with (P/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    audit={(r['cohort'],r['case_id'],r['target_id']):r for r in read('results/verification/tts_llm_verification.csv')}
    data=[]
    for manifest,cohort,folder in [('data/tts_cases.csv','baseline','results/tts_audio'),
                                   ('data/next/tts_next_cases.csv','next','results/next/audio')]:
        for row in read(manifest):
            item=ui.clip(row)
            item.update(src=f'../../{folder}/{row["case_id"]}.wav',blind=True,
                        why='Listen and type exactly what you hear before revealing the targets.')
            if not (P/folder/(row['case_id']+'.wav')).is_file():raise FileNotFoundError(item['src'])
            item['machine_marks']=[{'target':t['id'],'result':audit[cohort,row['case_id'],t['id']]['result'],
                 'heard':audit[cohort,row['case_id'],t['id']]['heard'],
                 'issues':audit[cohort,row['case_id'],t['id']]['target_spec_issues']} for t in item['targets']]
            data.append(item)
    full_data=data
    by_id={d['id']:d for d in data}
    human_flags={r['case_id'] for r in read('results/tts_scored_targets.csv')
                 if r['source']=='human' and r['final_result']!='correct'}
    flags={d['id'] for d in data if any(m['result']!='correct' for m in d['machine_marks'])}|human_flags
    selected=set(flags)
    reasons={cid:'flagged_by_llm_or_previous_human' for cid in selected}
    next_rows=read('data/next/tts_next_cases.csv')
    pairs={r['pair_id'] for r in next_rows if r['case_id'] in flags and r.get('pair_id')}
    for r in next_rows:
        if r.get('pair_id') in pairs and r['case_id'] not in selected:
            selected.add(r['case_id']);reasons[r['case_id']]='paired_raw_or_rewritten_comparison'
    if len(selected)>50:raise ValueError('More than 50 flagged/paired clips: selection needs explicit review')
    while len(selected)<50:
        cats=Counter(by_id[c]['category'] for c in selected)
        langs=Counter(by_id[c]['language'] for c in selected)
        candidates=[d for d in full_data if d['id'] not in selected and any(t['critical'] for t in d['targets'])]
        pick=min(candidates,key=lambda d:(cats[d['category']],langs[d['language']],d['id']))
        selected.add(pick['id']);reasons[pick['id']]='language_and_category_coverage'
    data=[d for d in full_data if d['id'] in selected]
    selection=P/'results/verification/human_priority50_selection.csv'
    with selection.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['case_id','language','category','selection_reason']);w.writeheader()
        w.writerows({'case_id':d['id'],'language':d['language'],'category':d['category'],'selection_reason':reasons[d['id']]} for d in data)
    template=ui.TEMPLATE
    marker='${showText?`<div class="text">${esc(d.text)}</div>'
    replacement='''${showText?`<details><summary>Provisional LLM findings (optional)</summary>
      <p>These are machine assessments. Record your own judgment; do not copy the LLM verdict.</p>
      ${(d.machine_marks||[]).map(m=>`<div><b>${esc(m.target)}</b>: ${esc(m.result)}; heard: ${esc(m.heard)}; specification issues: ${esc(m.issues)}</div>`).join("")}
      </details><div class="text">${esc(d.text)}</div>'''
    assert marker in template
    template=template.replace(marker,replacement)
    old='a.download=KEY.includes("mitigation")?"tts_fixes_filled.csv":"tts_listening_filled.csv"'
    assert old in template
    template=template.replace(old,'a.download="n1_tts_filled.csv"')
    template=template.replace('Type exactly what you heard (digits, amounts, signs)',
                              'Type exactly what you heard, including signs, each digit, and negations')
    def render(items,label):
        html=template.replace('__DATA__',json.dumps(items,ensure_ascii=False).replace('</','<\\/'))
        return html.replace('__TITLE__',label).replace('__KEY__','gnani-n1-tts-current-v2')
    html=render(data,'Human verification — 50 priority clips')
    (P/'data/listening/n1_tts_listen_all.html').write_text(render(full_data,'Full audio review bank — 164 clips'),encoding='utf8')
    path=P/'data/listening/n1_tts_listen.html'
    if path.exists():
        backup=P/'results/before_followup_fixes/data/listening/n1_tts_listen.html'
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():backup.write_bytes(path.read_bytes())
    path.write_text(html,encoding='utf-8')
    summary={'clips':len(data),'targets':sum(len(d['targets']) for d in data),
             'critical_targets':sum(bool(t['critical']) for d in data for t in d['targets']),
             'all_blind_first':all(d['blind'] for d in data),'export_filename':'n1_tts_filled.csv',
             'human_verification':'pending','full_bank_clips':len(full_data),'flagged_clips_included':len(flags),
             'selection':'targeted diagnostic sample, not a representative accuracy estimate'}
    (P/'results/verification/listening_page_coverage.json').write_text(json.dumps(summary,indent=2)+'\n')
    assert summary['clips']==50 and flags<=selected
    print(json.dumps(summary))

if __name__=='__main__':main()
