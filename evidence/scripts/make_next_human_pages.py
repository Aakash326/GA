"""N1 + N2 human pages (no API calls). Open them by double-click from data/listening/.

n1_tts_listen.html   - blind-first listening: the 66 next-stage TTS clips (N4) + the 19 benchmark Tamil/Kannada/
                       Marathi/Telugu prompts that only the judge scored. Export: n1_tts_filled.csv
n1_ref_check.html    - 30 random judge-accepted benchmark references (seed 7): does the text match the audio?
                       Export: n1_ref_check_filled.csv
n2_record.html       - the 24-utterance recording queue: record in the browser, saves 16 kHz mono WAVs
                       named <clip_id>__<speaker>.wav; move them to data/next/recordings/.
"""
import csv, json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_tts_listening_page as tl  # noqa: E402  (same template as the benchmark listening page)

P = tl.PROJECT
LIST = P / "data" / "listening"
read = lambda f: list(csv.DictReader((P / f).open(encoding="utf-8-sig", newline="")))
js = lambda d: json.dumps(d, ensure_ascii=False).replace("</", "<\\/")


def n1_tts():
    data = []
    for r in read("data/next/tts_next_cases.csv"):
        if (P / f"results/next/audio/{r['case_id']}.wav").exists():
            d = tl.clip(r)
            d.update(src=f"../../results/next/audio/{r['case_id']}.wav", blind=True, why=f"{r['input_form']} form of pair {r['pair_id']}")
            data.append(d)
    for r in read("data/tts_cases.csv"):
        if r["language"] in ("ta-IN", "kn-IN", "mr-IN", "te-IN") and (P / f"results/tts_audio/{r['case_id']}.wav").exists():
            data.append({**tl.clip(r), "why": "benchmark prompt scored by the judge only: needs a native listener"})
    tl.write(LIST / "n1_tts_listen.html", data, "N1 TTS Listening", key="gnani-n1-tts-v1")


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#2f5bd3}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#20201e;--text:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7f9cf5}}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}main{max-width:900px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:10px 0}.muted{color:var(--muted);font-size:13px}
button,input,textarea{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:6px;padding:4px 9px}
button.on{background:var(--accent);color:#fff}textarea{width:100%}audio{width:100%}.text{font-size:17px;margin:6px 0}
</style></head><body><main><h1>__TITLE__</h1><p class="muted">__HELP__</p>
<p>Your name/ID <input id="who" size="12"> <button id="export">Export CSV</button></p><div id="list"></div></main>
<script>const DATA=__DATA__,KEY="__KEY__";let st={};try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const who=document.getElementById("who");who.value=st._who||"";who.oninput=()=>{st._who=who.value;save()};
__BODY__
</script></body></html>"""

REF_JS = r"""
function render(){const L=document.getElementById("list");L.innerHTML="";DATA.forEach((d,i)=>{const s=st[d.id]||={};const c=document.createElement("div");c.className="card";
 c.innerHTML=`<b>${i+1}. ${esc(d.id)}</b> <span class="muted">${esc(d.language)}</span><audio controls preload="none" src="${esc(d.src)}"></audio>
 <div class="text">${esc(d.reference)}</div><button data-v="match" class="${s.v==="match"?"on":""}">matches exactly</button>
 <button data-v="differs" class="${s.v==="differs"?"on":""}">differs</button> <button data-v="cannot" class="${s.v==="cannot"?"on":""}">can't judge</button>
 <textarea rows="2" placeholder="If it differs: what is actually said">${esc(s.fix||"")}</textarea>`;
 c.querySelectorAll("button").forEach(b=>b.onclick=()=>{s.v=b.dataset.v;save();render()});c.querySelector("textarea").oninput=e=>{s.fix=e.target.value;save()};L.appendChild(c)})}
const cell=v=>/[",\n\r]/.test(v=String(v??""))?`"${v.replace(/"/g,'""')}"`:v;
document.getElementById("export").onclick=()=>{const rows=[["clip_id","listener","result","correction"],...DATA.map(d=>[d.id,who.value,(st[d.id]||{}).v||"",(st[d.id]||{}).fix||""])];
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["﻿"+rows.map(r=>r.map(cell).join(",")).join("\r\n")],{type:"text/csv"}));a.download="n1_ref_check_filled.csv";a.click()};
render();"""

REC_JS = r"""
let rec,chunks,cur;
async function wav16k(blob){const buf=await new AudioContext().decodeAudioData(await blob.arrayBuffer());
 const off=new OfflineAudioContext(1,Math.ceil(buf.duration*16000),16000),src=off.createBufferSource();src.buffer=buf;src.connect(off.destination);src.start();
 const x=(await off.startRendering()).getChannelData(0),v=new DataView(new ArrayBuffer(44+x.length*2)),w=(o,s)=>[...s].forEach((c,i)=>v.setUint8(o+i,c.charCodeAt(0)));
 w(0,"RIFF");v.setUint32(4,36+x.length*2,true);w(8,"WAVEfmt ");v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);
 v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);w(36,"data");v.setUint32(40,x.length*2,true);
 x.forEach((s,i)=>v.setInt16(44+i*2,Math.max(-1,Math.min(1,s))*32767,true));return new Blob([v],{type:"audio/wav"})}
function render(){const L=document.getElementById("list");L.innerHTML="";DATA.forEach((d,i)=>{const c=document.createElement("div");c.className="card";c.id="c"+d.id;
 c.innerHTML=`<b>${i+1}. ${esc(d.id)}</b> <span class="muted">${esc(d.language)} · ${esc(d.category)}</span><div class="text">${esc(d.script)}</div>
 <div class="muted">${esc(d.notes)}</div><button data-r>● record</button> <button data-s disabled>■ stop</button> <span data-msg class="muted">${(st[d.id]||{}).saved?"saved":""}</span><audio controls hidden></audio>`;
 const [r,s]=[c.querySelector("[data-r]"),c.querySelector("[data-s]")];
 r.onclick=async()=>{const m=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
  rec=new MediaRecorder(m);chunks=[];rec.ondataavailable=e=>chunks.push(e.data);r.disabled=true;s.disabled=false;
  rec.onstop=async()=>{m.getTracks().forEach(t=>t.stop());const w=await wav16k(new Blob(chunks)),u=URL.createObjectURL(w),a=c.querySelector("audio");a.src=u;a.hidden=false;
   const l=document.createElement("a");l.href=u;l.download=`${d.id}__${who.value||"speaker"}.wav`;l.click();(st[d.id]||={}).saved=true;save();c.querySelector("[data-msg]").textContent="saved (check Downloads)";r.disabled=false;s.disabled=true};rec.start()};
 s.onclick=()=>rec.stop();L.appendChild(c)})}
document.getElementById("export").onclick=()=>alert("Each recording downloads as a WAV when you press stop. Move them to data/next/recordings/.");
render();"""


def page(name, title, help_, data, body, key):
    (LIST / name).write_text(PAGE.replace("__TITLE__", title).replace("__HELP__", help_).replace("__DATA__", js(data))
                             .replace("__KEY__", key).replace("__BODY__", body), encoding="utf-8")
    print(f"wrote data/listening/{name} with {len(data)} items")


def main():
    n1_tts()
    acc = [r for r in read("results/asr_results.csv") if r["reference_status"] == "judge_accepted"]
    sample = random.Random(7).sample(acc, 30)
    page("n1_ref_check.html", "N1 Reference Check", "Listen, then say whether the text is exactly what is said "
         "(ignore punctuation and digits vs words for the same number). These references came from the judge.",
         [{"id": r["clip_id"], "language": r["language"], "reference": r["reference_transcript"],
           "src": "../../" + r["input_path"]} for r in sample], REF_JS, "gnani-n1-ref-v1")
    page("n2_record.html", "N2 Recording", "Quiet room, phone-to-mouth distance, natural speed. Read each line as "
         "you would say it on a call. If you say it differently, note what you said. Recording needs consent.",
         [{"id": r["clip_id"], "language": r["language"], "category": r["category"], "script": r["script_to_read"],
           "notes": r["notes"]} for r in read("data/next/asr_recording_queue.csv")], REC_JS, "gnani-n2-rec-v1")


if __name__ == "__main__":
    main()
