"""One Timbre 3.0 request with each of the 13 documented tags exactly once."""
import argparse,base64,hashlib,html,json,os,re,sys
from pathlib import Path
import soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
O=P/'results/all_tags_demo'
SECTIONS=[
 ('laugh','That was a wonderful surprise.'),
 ('giggle','You really made me smile.'),
 ('sigh','It has been a very long day.'),
 ('exhales','All right, I am ready to continue.'),
 ('sniffles','I think the cold weather got to me.'),
 ('yawns','I should probably get some sleep.'),
 ('coughs','Excuse me, let me try that again.'),
 ('clears throat','Thank you, may I have your attention.'),
 ('whispers','Keep this between you and me.'),
 ('shouting','Everyone, please move away from the road!'),
 ('excited','We did it! Our application has been approved!'),
 ('slow','Please listen carefully and take your time.'),
 ('pauses','Your request is complete. Thank you for waiting.')]
TEXT='Here is a quick expression demonstration.\n'+'\n'.join(f'<{tag}> {words}' for tag,words in SECTIONS)
assert re.findall(r'<([^>]+)>',TEXT)==[t for t,_ in SECTIONS]
assert len(set(t for t,_ in SECTIONS))==13


def build(live=False):
    import gnani_api as g
    O.mkdir(parents=True,exist_ok=True)
    g.ATTEMPTS=O/'attempts.jsonl';g.RAW=O/'raw';g.TTS_AUDIO=O/'audio'
    prior=P/'results/reconciliation/user_reported_spend.json'
    if not os.getenv('GNANI_SPENT_TO_DATE_INR') and prior.exists():os.environ['GNANI_SPENT_TO_DATE_INR']=str(json.loads(prior.read_text())['amount_inr'])
    prompt_path=P/'data/timbre_v3_all_tags.txt';prompt_path.write_text(TEXT+'\n',encoding='utf8')
    case='TAGS-ALL-13-EN-01'
    _,settings,fp=g.tts_request(TEXT,'en-IN','Tarika','timbre-v3.0',1.,48000)
    records=[json.loads(x) for x in g.ATTEMPTS.read_text(encoding='utf8').splitlines()] if g.ATTEMPTS.exists() else []
    good=[r for r in records if r.get('case_id')==case and r.get('fingerprint')==fp and r.get('ok') and r.get('audio_path')]
    if good:r=good[-1]
    elif live:
        r=g.synthesize(case,TEXT,'en-IN',run_tag='all_tags_demo',voice='Tarika',model='timbre-v3.0',speed=1.,sample_rate=48000,live=True)
    else:raise SystemExit('No cached demonstration: --live is required to generate it')
    if not r.get('ok') or not r.get('audio_path'):raise RuntimeError('TTS did not return usable audio: '+str(r.get('error')))
    original=P/r['audio_path'];samples,rate=sf.read(original,dtype='int16',always_2d=True)
    if not len(samples) or samples.shape[1]!=1:raise ValueError('No usable mono audio')
    wav=P/'timbre_v3_all_13_tags.wav'
    sf.write(wav,samples,rate,subtype='PCM_16')  # Finite header; unchanged decoded PCM.
    check,check_rate=sf.read(wav,dtype='int16',always_2d=True)
    if check_rate!=rate or not (check==samples).all():raise ValueError('PCM changed during WAV header repair')
    duration=len(samples)/rate
    meta=dict(case_id=case,request_id=r['request_id'],model='timbre-v3.0',voice='Tarika',language='en-IN',sample_rate=rate,
              duration_s=duration,request_latency_ms=r['latency_ms'],settings=settings,fingerprint=fp,
              prompt_path=prompt_path.relative_to(P).as_posix(),prompt_sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
              raw_audio_path=r['audio_path'],raw_audio_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
              audio_path=wav.name,audio_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),
              pcm_frames=len(samples),tags=[t for t,_ in SECTIONS],scope='One-request listening demonstration, not a scored quality benchmark')
    (O/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
    src='data:audio/wav;base64,'+base64.b64encode(wav.read_bytes()).decode()
    rows=''.join(f'<tr><td>{i}</td><td><code>&lt;{html.escape(tag)}&gt;</code></td><td>{html.escape(words)}</td></tr>' for i,(tag,words) in enumerate(SECTIONS,1))
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Timbre 3.0 — all 13 tags</title><style>body{{font:16px/1.65 system-ui;max-width:930px;margin:35px auto;padding:20px;color:#183247;background:#f5f8fa}}h1{{line-height:1.2}}.card{{background:white;padding:22px;border-radius:14px;border:1px solid #d6e2e8}}audio{{width:100%}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:9px;text-align:left;border-bottom:1px solid #d6e2e8}}code{{color:#955011}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}small{{color:#536879}}</style><h1>Timbre 3.0: all 13 tags in one clip</h1><p>Tarika · English · {rate//1000} kHz mono · {duration:.2f} seconds</p><div class="card"><audio controls preload="metadata" src="{src}"></audio><p>Follow the numbered tag order below. Each tag appears exactly once in the submitted text. Listen for the effect rather than assuming it rendered correctly.</p><small>This is one continuous API-generated clip. Only the WAV header was repaired; decoded PCM samples are unchanged. It is separate from the scored benchmark cohorts.</small></div><h2>Tag order and corresponding text</h2><table><tr><th>#</th><th>Tag</th><th>Text after the tag</th></tr>{rows}</table><details><summary>Exact submitted prompt</summary><pre>{html.escape(TEXT)}</pre></details><p><small>Tags apply until the next tag/end. The final &lt;pauses&gt; requests a pause before the closing sentence. This page embeds the complete WAV and works offline.</small></p></html>'''
    target=P/'timbre_v3_all_tags.html';target.write_text(page,encoding='utf8')
    print('Created one clip:',wav,flush=True)
    print('Duration:',round(duration,2),'seconds; tags:',len(meta['tags']),'; HTML:',target,flush=True)
    return meta


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');build(ap.parse_args().live)
