"""Build a portable, offline listening comparison from saved public TTS evidence.

Embeds original canonical PCM WAVs and the independently reconstructed streaming
playback. No synthesis, network requests, score changes, or audio edits are made.
"""
import base64,csv,hashlib,json,statistics,wave
from pathlib import Path

P=Path(__file__).resolve().parents[1]


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def build(project=None):
    project=Path(project or P);folder=project/'results/timbre_followup'
    rows=read(folder/'audio_results.csv');by_id={r['case_id']:r for r in rows}
    controlled_path=project/'results/report4/rest_latency_trials.csv'
    controlled=[]
    if controlled_path.exists():
        controlled=[dict(r,model=r['version'],voice=r['voice_id'],input_text=r['input_text'],latency_ms=r['request_total_ms'],duration_s=r['duration_s'],section='rest_latency') for r in read(controlled_path) if r['eligible_primary'].lower()=='true']
    rest_rows=controlled or rows;repeats=5 if controlled else 3
    streams={r['case_id']:r for r in read(folder/'stream_playback.csv')}
    assets={};manifest=[]
    def asset(path,case_id,kind,expected_hash=None):
        path=path.resolve()
        if not path.is_relative_to(project.resolve()):raise ValueError('Audio outside project')
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if expected_hash and digest!=expected_hash:raise ValueError('Changed audio: '+case_id)
        with wave.open(str(path),'rb') as wav:
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=24000:raise ValueError('Expected mono PCM16 at 24 kHz')
            duration=wav.getnframes()/wav.getframerate()
            if duration<=0:raise ValueError('Empty comparison audio')
        key=case_id+'-'+kind
        assets[key]='data:audio/wav;base64,'+base64.b64encode(raw).decode('ascii')
        manifest.append(dict(asset=key,case_id=case_id,kind=kind,source_path=path.relative_to(project).as_posix(),sha256=digest,bytes=len(raw),duration_s=duration))
        return key,duration
    def clip(row,kind='completed_audio',stream=None):
        cid=row['case_id'];path=project/row['audio_path']
        if stream:path=folder/stream['immediate_path']
        key,duration=asset(path,cid,kind,None if stream else row['audio_sha256'])
        result=dict(id=cid,model=row['model'],voice=row['voice'],text=row['input_text'],asset=key,duration=duration,
                    speechDuration=float(row['duration_s']),responseMs=float(row['latency_ms']))
        if stream:
            result.update(firstAudioMs=float(stream['first_audio_ms']),gaps=json.loads(stream['gaps']),
                          underruns=int(stream['underruns']),starvation=float(stream['starvation_s']))
        return result
    sets={'stream':[],'rest':[],'style':[]}
    for length in ['short','medium','long']:
        rest=[];stream=[]
        for key,model in [('3','timbre-v3.0'),('25','timbre-v2.5')]:
            group=[r for r in rest_rows if r['section']=='rest_latency' and r['model']==model and r['length']==length]
            if len(group)!=repeats:raise ValueError('Unexpected saved REST repetition count')
            median=statistics.median(float(r['latency_ms']) for r in group)
            selected=min(group,key=lambda r:abs(float(r['latency_ms'])-median))
            r=clip(selected);r.update(medianMs=median,runs=repeats,minMs=min(float(x['latency_ms']) for x in group),maxMs=max(float(x['latency_ms']) for x in group))
            rest.append(r)
            cid=f'NF-S-{key}-{length}';stream.append(clip(by_id[cid],'network_playback',streams[cid]))
        if rest[0]['text']!=rest[1]['text'] or stream[0]['text']!=stream[1]['text']:raise ValueError('Prompt mismatch')
        sets['rest'].append(dict(key=length,label=length.capitalize()+' prompt',text=rest[0]['text'],clips=rest))
        sets['stream'].append(dict(key=length,label=length.capitalize()+' prompt',text=stream[0]['text'],clips=stream))
    for style,label in [('neutral','Neutral'),('whispers','Whisper tag'),('excited','Excited tag')]:
        clips=[clip(by_id[f'NF-N-{key}-en' if style=='neutral' else f'NF-T-{key}-en-{style}']) for key in ['3','25']]
        if clips[0]['text']!=clips[1]['text']:raise ValueError('Style prompt mismatch')
        sets['style'].append(dict(key=style,label=label,text=clips[0]['text'],clips=clips))
    payload=json.dumps(dict(sets=sets,assets=assets),ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    output=project/'timbre_comparison.html'
    output.write_text(HTML.replace('__PAYLOAD__',payload).replace('__REST_REPEATS__',str(repeats)),encoding='utf8')
    record=dict(page=output.name,standalone=True,embedded_audio_clips=len(assets),comparison_pairs=sum(len(v) for v in sets.values()),
                rest_selection=f'Median-latency run separately per model/length; {repeats} repeats each, fixed selection rule',
                streaming_audio='Existing independent arrival-timed PCM reconstruction, including startup and starvation zeros',
                voices='Tarika (v3.0) and Kaveri (v2.5); different voices, no universal quality ranking',
                new_api_calls=0,assets=manifest)
    (folder/'comparison_manifest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    print(f'Created {output}: {len(assets)} embedded clips, {record["comparison_pairs"]} comparisons, {output.stat().st_size/1024**2:.1f} MB; no API calls')
    return record


HTML=r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; media-src data:; img-src data:; base-uri 'none'; form-action 'none'">
<title>Timbre 3.0 vs 2.5 — listen and compare</title>
<style>
:root{color-scheme:light;--ink:#152b3c;--muted:#526679;--blue:#165e78;--teal:#096b5d;--orange:#a34a14;--line:#d8e2e8;--paper:#fff;--gap:#c03938}
*{box-sizing:border-box}body{margin:0;background:#f3f6f8;color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}button,select{font:inherit}button{cursor:pointer}button:focus-visible,select:focus-visible,summary:focus-visible,audio:focus-visible{outline:3px solid #236dba;outline-offset:4px}button:disabled{opacity:.5;cursor:default}
.shell{max-width:1180px;margin:auto;padding:38px 26px 45px}.eyebrow{font-size:12px;letter-spacing:.16em;font-weight:750;color:var(--blue);text-transform:uppercase}h1{font-size:clamp(30px,5vw,49px);line-height:1.15;letter-spacing:-.045em;margin:12px 0}h2,h3,p{margin:0}.lead{max-width:780px;color:var(--muted);font-size:18px}.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}.chip{background:#e5eef2;color:#355365;padding:5px 10px;border-radius:20px;font-size:12px;font-weight:650}.takeaway{margin:26px 0 24px;padding:18px 22px;border:1px solid #bad6d0;border-left:4px solid var(--teal);background:#edf7f3;border-radius:12px}.takeaway p{color:#315c52;font-size:14px;margin-top:4px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:10px}.tab{border:0;background:transparent;padding:10px 17px;border-radius:9px;color:var(--muted);font-weight:650}.tab[aria-selected=true]{background:var(--ink);color:white}.panel{margin-top:22px}.toolbar{display:flex;align-items:end;justify-content:space-between;gap:16px;flex-wrap:wrap}label{display:block;color:var(--muted);font-size:12px;font-weight:700;margin-bottom:5px}select{background:white;color:var(--ink);border:1px solid #aabcc8;border-radius:8px;padding:9px 40px 9px 12px;min-width:210px}.buttons{display:flex;gap:8px;flex-wrap:wrap}.btn{background:var(--blue);color:white;border:1px solid var(--blue);padding:9px 14px;border-radius:8px;font-weight:650;font-size:14px}.btn.secondary{background:white;color:var(--ink);border-color:#aabcc8}.mode-note{margin:17px 0;color:var(--muted);font-size:14px;max-width:980px}.prompt{background:#eaf0f4;border-radius:10px;padding:14px 18px;margin-bottom:18px}.prompt summary{cursor:pointer;font-size:13px;font-weight:650;color:#365467}.prompt p{font-size:14px;margin-top:9px;white-space:pre-wrap}.prompt:not([open]) summary{margin:0}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card{background:white;border:1px solid var(--line);border-radius:16px;padding:22px;min-width:0;box-shadow:0 3px 8px #18364d06}.card.v3{border-top:4px solid var(--orange)}.card.v25{border-top:4px solid var(--teal)}.card-top{display:flex;justify-content:space-between;gap:10px;align-items:center}.model{font-size:25px;letter-spacing:-.025em;font-weight:750}.voice{color:var(--muted);font-size:13px}.pill{border-radius:6px;padding:4px 9px;background:#faf0e7;color:#824016;font-size:12px;font-weight:700}.v25 .pill{background:#e4f4ed;color:#125e48}.measure{margin-top:18px;display:grid;grid-template-columns:1fr 1fr;gap:12px}.metric .number{font-size:31px;letter-spacing:-.035em;font-weight:730;line-height:1.2}.metric .caption{font-size:12px;color:var(--muted);margin-top:4px}.audio-label{margin-top:22px;font-size:13px;font-weight:650}audio{display:block;width:100%;height:44px;margin:9px 0 8px}.listen-hint{font-size:13px;color:var(--muted);min-height:42px}.timeline-wrap{margin:14px 0 10px}.timeline{width:100%;height:64px;display:block}.legend{display:flex;gap:13px;flex-wrap:wrap;font-size:11px;color:var(--muted)}.dot{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px}.wait-btn{margin-top:12px;width:100%}.status{font-size:13px;color:var(--blue);min-height:24px;margin-top:9px}.detail{border-top:1px solid #edf1f4;margin-top:14px;padding-top:12px;font-size:12px;color:var(--muted)}.detail summary{cursor:pointer;font-weight:650}.detail p{margin-top:8px;overflow-wrap:anywhere}.range{font-size:12px;color:var(--muted);margin-top:7px}.footgrid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:26px}.footbox{background:#eaf0f4;padding:18px 20px;border-radius:12px}.footbox h3{font-size:14px;margin-bottom:6px}.footbox p{font-size:13px;color:var(--muted)}.global-status{font-size:13px;color:var(--blue);min-height:22px;margin-top:9px}footer{margin-top:25px;color:var(--muted);font-size:12px}#error{color:#9d2424;font-weight:650}noscript{display:block;padding:20px;background:white}
@media(max-width:730px){.shell{padding:25px 16px}.cards,.footgrid{grid-template-columns:1fr}.card{padding:18px}.tab{padding:9px 11px;font-size:13px}.lead{font-size:16px}.toolbar{align-items:start}.buttons .btn{font-size:13px}.model{font-size:23px}}
</style>
</head>
<body><main class="shell">
<div class="eyebrow">Gnani speech evaluation / Listening room</div>
<h1>Timbre 3.0 <span style="color:#8193a0;font-weight:400">vs</span> 2.5</h1>
<p class="lead">Same prompts. Two model configurations. Hear the playback gaps, compare the response wait, and decide how each voice sounds.</p>
<div class="chips"><span class="chip">18 embedded clips · 9 comparisons</span><span class="chip">24 kHz · mono PCM</span><span class="chip">Works offline · no API calls</span><span class="chip">Collected 15 Nov 2026</span></div>
<aside class="takeaway"><strong>V2.5 was faster and continuous in the tested streaming samples.</strong><p>This is a configuration comparison: Tarika on v3.0 and Kaveri on v2.5. Different voices and small samples prevent a universal model-quality ranking.</p></aside>
<nav class="tabs" role="tablist" aria-label="Comparison type"><button class="tab" id="tab-stream" role="tab" aria-selected="true" aria-controls="comparison-panel" data-mode="stream">1 · Streaming gaps</button><button class="tab" id="tab-rest" role="tab" aria-selected="false" tabindex="-1" aria-controls="comparison-panel" data-mode="rest">2 · Non-streaming REST</button><button class="tab" id="tab-style" role="tab" aria-selected="false" tabindex="-1" aria-controls="comparison-panel" data-mode="style">3 · Voice &amp; expression</button></nav>
<section id="comparison-panel" class="panel" role="tabpanel" aria-labelledby="tab-stream">
<div class="toolbar"><div><label for="sample">Choose a matched pair</label><select id="sample"></select></div><div class="buttons"><button class="btn" id="sequence">Play 3.0 → 2.5</button><button class="btn secondary" id="stop">Stop &amp; reset</button></div></div>
<div class="global-status" id="global-status" role="status"></div><p id="mode-note" class="mode-note"></p>
<details class="prompt" id="prompt-box" open><summary>Text sent to both models</summary><p id="prompt"></p></details>
<div id="cards" class="cards"></div><p id="error" role="alert"></p>
</section>
<div class="footgrid"><aside class="footbox"><h3>What to listen for</h3><p id="listen-for"></p></aside><aside class="footbox"><h3>How to interpret this page</h3><p>The streaming files reconstruct saved chunk arrivals; they are not live handset recordings. REST files contain completed audio. Speech quality, response latency and network starvation are different measurements. No loudness normalization, denoising or speed changes were added here.</p></aside></div>
<footer>English listening examples from distinct saved cohorts. Six earlier SSE traces; __REST_REPEATS__ controlled REST repeats per model and length. The earlier follow-up recorded six empty v3.0 outputs and one recovered HTTP 500; the later listening set added another empty output. This page plays successful clips. Native-listener verification remains necessary for expression and naturalness.</footer>
<noscript>Enable JavaScript to select and play the embedded audio comparisons. No internet connection is needed.</noscript>
</main>
<script id="comparison-data" type="application/json">__PAYLOAD__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('comparison-data').textContent);
const $=id=>document.getElementById(id), sec=ms=>(ms/1000).toFixed(2)+' s';
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let mode='stream', current=[], players=[], waits=[], sequenceCurrent=null, epoch=0;
const notes={
stream:'Start with the short prompt. These files include measured dispatch-to-first-chunk waiting and any later network starvation, reconstructed as silence. The tiny first chunk followed by a gap is easiest to hear in the v3.0 short sample. This is saved evidence, not a new live request.',
rest:'The players below contain completed REST audio, so pressing Play starts the saved clip immediately. “Replay response wait” first waits the selected run’s recorded dispatch-to-full-body interval, then plays the clip. This is a timed demonstration, not a new API measurement. Each clip is its model’s median-latency run from __REST_REPEATS__ repeats.',
style:'The neutral, whisper and excited pairs use the same input text for both models. V3.0 documents support for the inline tags; v2.5 is a tag-stripping control. Compare cadence, stress, pronunciation and the second sentence’s delivery. No naturalness winner is assigned here.'};
const hints={
stream:'Listen for the initial wait, any small first sound and the interruption before continuous speech. The red timeline intervals are missing network audio, not planned sentence pauses. All three displayed v3.0 traces underrun; all three v2.5 controls remain continuous.',
rest:'First compare the clean speech with native Play. Then use the response-wait buttons to experience why a fast-sounding voice can still feel slow in a conversation. Faster generation does not by itself establish more natural speech.',
style:'Listen once without reading the prompt, then check whether the intended cue is audible while the words stay clear. Tags can alter delivery without improving every aspect of naturalness. The model judge’s ratings were provisional; your listening matters here.'};

function cancelWait(i){const w=waits[i];if(w){clearTimeout(w.timer);clearInterval(w.interval);waits[i]=null;}const b=$('wait-'+i);if(b){b.textContent='Replay response wait → audio';b.setAttribute('aria-pressed','false');}}
function stopAll(reset=true){epoch++;sequenceCurrent=null;players.forEach((p,i)=>{cancelWait(i);p.pause();if(reset)p.currentTime=0;const s=$('status-'+i);if(s)s.textContent='';});$('global-status').textContent='';}
function fail(message){$('error').textContent=message;}
function startAudio(i){const p=players[i];if(!p)return;cancelWait(i);p.currentTime=0;return p.play().catch(()=>{sequenceCurrent=null;fail('Playback was blocked or unavailable. Try the audio player’s Play button.');});}
function timeline(c,i){
 if(mode!=='stream')return '';
 const W=700, full=c.duration, x=s=>Math.max(0,Math.min(W,s/full*W));
 let rects=`<rect x="0" y="12" width="700" height="17" rx="4" fill="#a8bec3"/><rect x="0" y="12" width="${x(c.firstAudioMs/1000)}" height="17" fill="#d6dde3"/>`;
 for(const g of c.gaps)rects+=`<rect x="${x(g.start_s)}" y="12" width="${Math.max(.8,x(g.start_s+g.duration_s)-x(g.start_s))}" height="17" fill="#c03938"/>`;
 return `<div class="timeline-wrap"><svg class="timeline" viewBox="0 0 700 64" role="img" aria-label="Playback timeline, ${c.underruns} network gaps; ${c.starvation.toFixed(3)} seconds total starvation"><title>Gray is startup; muted teal is delivered audio including natural pauses; red is reconstructed network starvation.</title>${rects}<line id="cursor-${i}" x1="0" x2="0" y1="7" y2="34" stroke="#18354b" stroke-width="3"/><text x="0" y="53" fill="#526679" font-size="16">0 s</text><text x="700" y="53" text-anchor="end" fill="#526679" font-size="16">${full.toFixed(2)} s</text></svg><div class="legend"><span><i class="dot" style="background:#d6dde3"></i>Startup wait</span><span><i class="dot" style="background:#a8bec3"></i>Delivered audio</span><span><i class="dot" style="background:#c03938"></i>Network gap</span></div></div>`;
}
function card(c,i){
 const v3=i===0;let a,b,hint,detail,pill;
 if(mode==='stream'){
   a=[sec(c.firstAudioMs),'First playable PCM chunk'];b=[String(c.underruns),'Underruns after playback starts'];
   pill=c.underruns?'Gaps reconstructed':'No underruns';
   hint=c.underruns?`${c.starvation.toFixed(3)} s total network starvation. Watch the red intervals as you listen.`:'Continuous after startup in this saved trace. Natural speech pauses may still occur.';
   detail='Gap intervals from dispatch: '+(c.gaps.length?c.gaps.map(g=>`${g.start_s.toFixed(3)}–${(g.start_s+g.duration_s).toFixed(3)} s`).join('; '):'none')+'.';
 }else if(mode==='rest'){
   a=[sec(c.responseMs),'Full-response wait · selected run'];b=[c.speechDuration.toFixed(2)+' s','Completed audio duration'];pill='Median-latency run';
   hint='The saved clip has no added response-wait silence. Use the button below to replay that wait separately.';
   detail=`${c.runs}-run response range ${sec(c.minMs)}–${sec(c.maxMs)}; median ${sec(c.medianMs)}. Selection used latency only, not perceived voice quality.`;
 }else{
   a=[c.speechDuration.toFixed(2)+' s','Completed audio duration'];b=[sec(c.responseMs),'Full-response wait · one request'];
   pill=$('sample').value==='neutral'?'Neutral input':v3?'Expression-capable':'Tag-stripping control';
   hint=$('sample').value==='neutral'?'Listen for rhythm, pronunciation and natural pauses.':v3?'Listen for the requested cue after the first sentence.':'The tag is documented to be removed; normal speaking style is the expected control.';
   detail='Expression comparisons use one request per condition. Different voices and synthesis variability limit conclusions.';
 }
 return `<article class="card ${v3?'v3':'v25'}"><div class="card-top"><div><h2 class="model">Timbre ${v3?'3.0':'2.5'}</h2><p class="voice">Voice: ${escapeHTML(c.voice)} · English</p></div><span class="pill">${pill}</span></div><div class="measure"><div class="metric"><div class="number">${a[0]}</div><div class="caption">${a[1]}</div></div><div class="metric"><div class="number">${b[0]}</div><div class="caption">${b[1]}</div></div></div><p class="audio-label">${mode==='stream'?'Arrival-timed playback':'Completed speech audio'}</p><audio id="audio-${i}" controls preload="metadata" aria-label="${escapeHTML(c.model)} ${escapeHTML(c.voice)} audio"></audio><p class="listen-hint">${hint}</p>${timeline(c,i)}${mode==='rest'?`<button class="btn secondary wait-btn" id="wait-${i}" aria-pressed="false">Replay response wait → audio</button>`:''}<p class="status" id="status-${i}" role="status"></p><details class="detail"><summary>Measurement details</summary><p>${detail}</p><p>Saved case: ${escapeHTML(c.id)}. Mono PCM16, 24 kHz. The clip has not been denoised, normalized or time-stretched.</p></details></article>`;
}
function render(){
 stopAll();$('error').textContent='';const group=DATA.sets[mode].find(x=>x.key===$('sample').value);current=group.clips;
 $('mode-note').textContent=notes[mode];$('listen-for').textContent=hints[mode];$('prompt').textContent=group.text;$('prompt-box').open=group.text.length<180;
 $('cards').innerHTML=current.map(card).join('');players=current.map((c,i)=>$('audio-'+i));waits=[];
 players.forEach((p,i)=>{
   p.src=DATA.assets[current[i].asset];
   p.addEventListener('play',()=>{cancelWait(i);if(sequenceCurrent!==null&&sequenceCurrent!==i)sequenceCurrent=null;players.forEach((q,j)=>{if(i!==j){q.pause();cancelWait(j);const s=$('status-'+j);if(s)s.textContent='';}});$('status-'+i).textContent='Playing saved audio.';});
   p.addEventListener('pause',()=>{if(!p.ended&&!waits[i])$('status-'+i).textContent=p.currentTime?'Paused.':'';});
   p.addEventListener('ended',()=>{$('status-'+i).textContent='Finished.';if(sequenceCurrent===0&&i===0){sequenceCurrent=1;$('global-status').textContent='Now playing Timbre 2.5.';startAudio(1);}else{sequenceCurrent=null;$('global-status').textContent='';}});
   p.addEventListener('timeupdate',()=>{const cursor=$('cursor-'+i);if(cursor){const x=Math.min(700,700*p.currentTime/current[i].duration);cursor.setAttribute('x1',x);cursor.setAttribute('x2',x);}});
   p.addEventListener('error',()=>fail('An embedded audio clip could not be opened. Use a recent Chrome, Edge or Firefox browser.'));
   const button=$('wait-'+i);if(button)button.addEventListener('click',()=>{
     if(waits[i]){stopAll();return;}stopAll();const token=epoch,delay=current[i].responseMs,started=performance.now();button.textContent='Cancel recorded wait';button.setAttribute('aria-pressed','true');$('status-'+i).textContent=`Replaying the recorded ${sec(delay)} response wait…`;
     const interval=setInterval(()=>{const left=Math.max(0,(delay-performance.now()+started)/1000);button.textContent=`Waiting ${left.toFixed(1)} s · cancel`;},100);
     const timer=setTimeout(()=>{if(token!==epoch)return;cancelWait(i);startAudio(i);},delay);waits[i]={timer,interval};
   });
 });
}
function selectMode(next){
 mode=next;document.querySelectorAll('.tab').forEach(b=>{const active=b.dataset.mode===mode;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;});
 $('comparison-panel').setAttribute('aria-labelledby','tab-'+mode);$('sample').replaceChildren(...DATA.sets[mode].map(s=>new Option(s.label,s.key)));render();
}
document.querySelectorAll('.tab').forEach((b,i)=>{
 b.addEventListener('click',()=>selectMode(b.dataset.mode));
 b.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const tabs=Array.from(document.querySelectorAll('.tab'));let j=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length;selectMode(tabs[j].dataset.mode);tabs[j].focus();}});
});
$('sample').addEventListener('change',render);$('stop').addEventListener('click',()=>stopAll());
$('sequence').addEventListener('click',()=>{stopAll();sequenceCurrent=0;$('global-status').textContent='Playing Timbre 3.0, then Timbre 2.5. No new API request.';startAudio(0);});
window.addEventListener('pagehide',()=>stopAll());selectMode('stream');
</script></body></html>'''


if __name__=='__main__':build()
