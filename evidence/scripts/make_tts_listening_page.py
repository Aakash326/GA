"""Generate data/listening/tts_listen.html (all clips) and tts_listen_priority.html (30 key clips) for Stage 10 (human scoring of Timbre audio).

- Plays results/tts_audio/<case>.wav (run1, the baseline clip).
- Number/ID prompts are BLIND first: the listener types what they heard before the text and targets are shown.
- Per target: correct / wrong / ambiguous (ambiguous counts as not correct in the strict score).
- Per clip: naturalness 1-5, prosody 1-5, content complete, meaning preserved, artifacts, comment.
- Order is shuffled per listener ID (stable), as the plan asks for randomised playback.
Export -> data/listening/tts_listening_filled.csv (one row per clip x target).
"""
import csv
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "data" / "listening" / "tts_listen.html"
BLIND_CATEGORIES = {"numeric", "identifiers"}
BLIND_IDS = {"T34", "T35", "T37", "T41", "T79"}


PRIORITY_OUT = PROJECT / "data" / "listening" / "tts_listen_priority.html"
MITIGATION_OUT = PROJECT / "data" / "listening" / "tts_listen_fixes.html"
# The 30 clips that matter most and can be judged by an English/Hindi listener, with the reason for each.
PRIORITY = {
    "T02": "amount with paise: ₹1,57,890.50", "T03": "date and year", "T34": "negative sign: −2.5%",
    "T39": "tiny amount: ₹0.05 (five paise)", "T40": "negative vs positive amount + 'not'", "T41": "fifteen vs fifty + 'not'",
    "T43": "₹10,00,000 must be ten lakh", "T44": "times 9:05 AM and 12:30 PM", "T45": "3rd vs 30th November",
    "T49": "four leading zeros: 000042", "T51": "letter O vs zero: AB10O0", "T52": "leading zeros: 0070",
    "T54": "ticket number read digit by digit", "T57": "16-digit reference, every digit", "T58": "4821 vs 4812 + 'not'",
    "T27": "'Do not share your OTP': the 'not' must be heard", "T61": "Hindi negation: confirm नहीं",
    "T80": "'Do not cancel the payment'", "T06": "KYC as raw text", "T38": "KYC written as K Y C (compare with T06)",
    "T70": "NEFT and UPI acronyms", "T11": "Hindi sentence with English words", "T12": "Hindi written in English letters",
    "T36": "same sentence as T12 in Hindi script (compare)", "T62": "romanised Hindi; fastest clip, check for skipped words",
    "T60": "₹1,250 inside a Hindi sentence", "T32": "plain Hindi baseline", "T29": "'read' now vs 'read' yesterday",
    "T33": "one-word reply 'Yes.'", "T37": "amount spelled out in words (compare with T01, already confirmed)",
}


def clip(r):
    return {"id": r["case_id"], "category": r["category"], "language": r["language"], "text": r["input_text"],
            "src": f"../../results/tts_audio/{r['case_id']}.wav",
            "blind": r["category"] in BLIND_CATEGORIES or r["case_id"] in BLIND_IDS,
            "targets": json.loads(r["expected_targets_json"] or "[]"),
            "variants": json.loads(r["accepted_variants_json"] or "{}"), "why": PRIORITY.get(r["case_id"], "")}


def write(path, data, title, key="gnani-tts-listening-v1"):
    html = (TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__TITLE__", title).replace("__KEY__", key))
    path.write_text(html, encoding="utf-8")
    print(f"wrote {path.relative_to(PROJECT)} with {len(data)} clips ({sum(d['blind'] for d in data)} blind-first)")


def main() -> None:
    with (PROJECT / "data" / "tts_cases.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (PROJECT / "results" / "tts_audio" / f"{r['case_id']}.wav").exists()]
    write(OUT, [clip(r) for r in rows], "TTS Listening Scores")
    missing = set(PRIORITY) - {r["case_id"] for r in rows}
    if missing:
        raise SystemExit(f"priority clips without audio: {sorted(missing)}")
    write(PRIORITY_OUT, [clip(r) for r in rows if r["case_id"] in PRIORITY], "TTS Priority Listening")

    mit_file = PROJECT / "data" / "tts_mitigation_cases.csv"
    if mit_file.exists():
        by_id = {r["case_id"]: r for r in rows}
        with mit_file.open(encoding="utf-8-sig", newline="") as fh:
            mit = [r for r in csv.DictReader(fh) if (PROJECT / "results" / "tts_audio" / f"{r['case_id']}.wav").exists()]
        data = []
        for r in mit:
            d = clip(r)
            base = by_id[r["paired_with"]]
            d.update(blind=False, why=("Rewritten input. " if r["category"] == "mitigation" else "Other voice/model. ") + r["notes"].split(": ", 1)[1].split(". Same", 1)[0],
                     compare=f"../../results/tts_audio/{base['case_id']}.wav", compare_id=base["case_id"],
                     compare_text=base["input_text"])
            data.append(d)
        write(MITIGATION_OUT, data, "TTS Fix Check", key="gnani-tts-mitigation-v1")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#2f5bd3;--ok:#1f7a45;--okbg:#e5f4ea;--bad:#b4371f;--badbg:#fbe9e5;--amb:#7a6a1f;--ambbg:#f6f0d8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--text:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7f9cf5;--ok:#7fd39b;--okbg:#1d3326;--bad:#f19a85;--badbg:#3a221c;--amb:#e3cf7a;--ambbg:#38321a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px}
.bar{max-width:940px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}h1{font-size:18px;margin:0 10px 0 0}
.progress{flex:1;min-width:140px;height:8px;background:var(--line);border-radius:4px;overflow:hidden}.progress>div{height:100%;background:var(--accent);width:0}
button,select,input[type=text]{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:6px;padding:4px 9px}
button{cursor:pointer}button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
main{max-width:940px;margin:0 auto;padding:16px}.help{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 12px}.card.done{border-left:5px solid var(--ok)}
.id{font-weight:650;font-family:ui-monospace,Consolas,monospace}.tag{font-size:12px;color:var(--muted)}
audio{width:100%;margin:8px 0 4px;height:36px}.text{font-size:17px;padding:8px 10px;background:var(--bg);border-radius:6px;margin:6px 0;word-break:break-word}
.blindbox{border:1px dashed var(--accent);border-radius:8px;padding:8px 10px;margin:6px 0}
.tg{border-top:1px solid var(--line);padding:6px 0;display:grid;grid-template-columns:1fr auto;gap:4px 10px;align-items:start}
.tg .acc{font-size:12px;color:var(--ok)}.tg .rej{font-size:12px;color:var(--bad)}
.seg button{padding:3px 8px;font-size:13px}.seg .on-correct{background:var(--okbg);color:var(--ok);border-color:var(--ok)}
.seg .on-wrong{background:var(--badbg);color:var(--bad);border-color:var(--bad)}.seg .on-ambiguous{background:var(--ambbg);color:var(--amb);border-color:var(--amb)}
.row{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin-top:8px}.row label{font-size:13px;color:var(--muted)}
.scale button{width:34px;padding:3px 0}.scale .on{background:var(--accent);color:#fff;border-color:var(--accent)}
.crit{font-size:11px;padding:0 6px;border-radius:9px;background:var(--badbg);color:var(--bad)}.minor{font-size:11px;padding:0 6px;border-radius:9px;background:var(--line);color:var(--muted)}
textarea{width:100%;font:inherit;border:1px solid var(--line);border-radius:6px;padding:6px 8px;background:var(--bg);color:var(--text);margin-top:6px}
.hide{display:none}.anchors{font-size:12px;color:var(--muted)}
@media (max-width:560px){.tg{grid-template-columns:1fr}}
</style></head><body>
<header><div class="bar"><h1>__TITLE__</h1><div class="progress"><div id="prog"></div></div><span class="tag" id="count"></span>
<label class="tag">listener <input type="text" id="listener" style="width:70px" placeholder="R1"></label>
<label class="tag">languages <input type="text" id="langs" style="width:110px" placeholder="en,hi"></label>
<label class="tag"><input type="checkbox" id="open"> only unfinished</label>
<button class="primary" id="export">Export CSV</button><button id="importBtn">Import</button><input type="file" id="importFile" accept=".csv" class="hide"></div></header>
<main><p class="help">Use headphones, same volume throughout. <b>Blind clips</b> (numbers, IDs): type exactly what you heard
<i>before</i> pressing Reveal. Then mark each target <b>Correct</b> only if it matches an accepted reading;
<b>Ambiguous</b> if you could not tell (counts as not correct). Rate every clip:</p>
<p class="anchors"><b>Naturalness</b> 1 robotic/unpleasant · 2 strained · 3 understandable but synthetic · 4 mostly natural · 5 natural and fluent.
<b>Prosody</b> 1 obstructs understanding · 2 frequent disruptive pauses/stress · 3 noticeable issues · 4 minor issues · 5 consistently appropriate.
Skip prompts in a language you don't speak (mark "can't judge").</p>
<div id="list"></div></main>
<script>
const DATA=__DATA__,KEY="__KEY__";
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};
const S=id=>(st[id]||={targets:{},nat:"",pros:"",complete:"",meaning:"",artifacts:[],comment:"",heard:"",revealed:false,blindTyped:false,skip:false});
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const lis=document.getElementById("listener"),langs=document.getElementById("langs");
try{lis.value=localStorage.getItem(KEY+"-l")||"";langs.value=localStorage.getItem(KEY+"-g")||""}catch(e){}
lis.oninput=()=>{try{localStorage.setItem(KEY+"-l",lis.value)}catch(e){};render()};langs.oninput=()=>{try{localStorage.setItem(KEY+"-g",langs.value)}catch(e){}};
function order(){const seed=[...(lis.value||"R1")].reduce((a,c)=>(a*31+c.charCodeAt(0))>>>0,7);let x=seed||1;
 const rnd=()=>{x^=x<<13;x>>>=0;x^=x>>17;x^=x<<5;x>>>=0;return x/4294967296};
 const a=[...DATA];for(let i=a.length-1;i>0;i--){const j=Math.floor(rnd()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a}
function complete(d){const s=S(d.id);if(s.skip)return true;if(d.blind&&!s.revealed)return false;
 return d.targets.every(t=>s.targets[t.id])&&s.nat&&s.pros&&s.complete&&s.meaning}
function render(){const list=document.getElementById("list");list.innerHTML="";const only=document.getElementById("open").checked;
 order().forEach((d,i)=>{const s=S(d.id);if(only&&complete(d))return;const showText=!d.blind||s.revealed;
  const card=document.createElement("div");card.className="card"+(complete(d)?" done":"");card.id="c-"+d.id;
  card.innerHTML=`<div><span class="id">${i+1}. ${esc(d.id)}</span> <span class="tag">${esc(d.category)} · ${esc(d.language)}${d.blind?" · blind first":""}</span></div>
  ${d.why?`<div class="tag"><b>Listen for:</b> ${esc(d.why)}</div>`:""}
  <audio controls preload="none" src="${esc(d.src)}"></audio>
  ${d.compare?`<div class="tag">Original raw-input clip ${esc(d.compare_id)} for comparison: “${esc(d.compare_text)}”</div><audio controls preload="none" src="${esc(d.compare)}"></audio>`:""}
  ${d.blind&&!s.revealed?`<div class="blindbox"><textarea rows="2" data-heard placeholder="Type exactly what you heard (digits, amounts, signs)">${esc(s.heard)}</textarea>
   <button data-reveal>Reveal text and targets</button></div>`:""}
  ${showText?`<div class="text">${esc(d.text)}</div>${d.blind?`<div class="tag">You heard: ${esc(s.heard)||"(nothing typed)"}${s.blindTyped?"":" (typed after reveal: not blind)"}</div>`:""}
  ${d.targets.map(t=>{const v=d.variants[t.id]||{accept:[],reject:[]},on=s.targets[t.id]||"";return `<div class="tg"><div><b>${esc(t.id)}</b> ${t.critical?'<span class="crit">critical</span>':'<span class="minor">minor</span>'} must hear: ${esc(t.must_hear)}
   <div class="acc">accept: ${v.accept.map(esc).join(" · ")}</div><div class="rej">not correct: ${v.reject.map(esc).join(" · ")}</div></div>
   <div class="seg" data-t="${esc(t.id)}">${["correct","wrong","ambiguous"].map(x=>`<button data-v="${x}" class="${on===x?"on-"+x:""}">${x}</button>`).join(" ")}</div></div>`}).join("")}
  <div class="row"><label>Naturalness</label><span class="scale" data-k="nat">${[1,2,3,4,5].map(n=>`<button class="${s.nat==n?"on":""}">${n}</button>`).join("")}</span>
   <label>Prosody</label><span class="scale" data-k="pros">${[1,2,3,4,5].map(n=>`<button class="${s.pros==n?"on":""}">${n}</button>`).join("")}</span></div>
  <div class="row"><label>Content complete</label><select data-k="complete">${["","yes","no"].map(o=>`<option ${s.complete===o?"selected":""}>${o}</option>`).join("")}</select>
   <label>Meaning preserved</label><select data-k="meaning">${["","yes","no"].map(o=>`<option ${s.meaning===o?"selected":""}>${o}</option>`).join("")}</select>
   <label>Artifacts</label>${["click","distortion","clipping","silence","broken ending"].map(a=>`<label><input type="checkbox" data-art="${a}" ${s.artifacts.includes(a)?"checked":""}> ${a}</label>`).join("")}</div>
  <textarea rows="2" data-comment placeholder="Evidence: what was missing/added/repeated, with a timestamp if you can">${esc(s.comment)}</textarea>`:""}
  <div class="row"><label><input type="checkbox" data-skip ${s.skip?"checked":""}> can't judge (language or audio)</label></div>`;
  wire(card,d);list.appendChild(card)});progress()}
function touch(d){S(d.id).at=new Date().toISOString();save();progress();const c=document.getElementById("c-"+d.id);if(c)c.classList.toggle("done",complete(d))}
function wire(card,d){const s=S(d.id);
 const h=card.querySelector("[data-heard]");if(h)h.oninput=()=>{s.heard=h.value;s.blindTyped=h.value.trim()!=="";touch(d)};
 const r=card.querySelector("[data-reveal]");if(r)r.onclick=()=>{s.revealed=true;touch(d);render()};
 card.querySelectorAll(".seg").forEach(g=>g.querySelectorAll("button").forEach(b=>b.onclick=()=>{s.targets[g.dataset.t]=s.targets[g.dataset.t]===b.dataset.v?"":b.dataset.v;
  g.querySelectorAll("button").forEach(x=>x.className=s.targets[g.dataset.t]===x.dataset.v?"on-"+x.dataset.v:"");touch(d)}));
 card.querySelectorAll(".scale").forEach(g=>g.querySelectorAll("button").forEach(b=>b.onclick=()=>{s[g.dataset.k]=b.textContent;
  g.querySelectorAll("button").forEach(x=>x.className=x===b?"on":"");touch(d)}));
 card.querySelectorAll("select[data-k]").forEach(x=>x.onchange=()=>{s[x.dataset.k]=x.value;touch(d)});
 card.querySelectorAll("[data-art]").forEach(x=>x.onchange=()=>{s.artifacts=x.checked?[...new Set([...s.artifacts,x.dataset.art])]:s.artifacts.filter(a=>a!==x.dataset.art);touch(d)});
 const c=card.querySelector("[data-comment]");if(c)c.oninput=()=>{s.comment=c.value;touch(d)};
 card.querySelector("[data-skip]").onchange=e=>{s.skip=e.target.checked;touch(d)};
 card.querySelector("audio").addEventListener("play",e=>document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()}))}
function progress(){const n=DATA.filter(complete).length;document.getElementById("prog").style.width=(100*n/DATA.length)+"%";document.getElementById("count").textContent=`${n} / ${DATA.length} clips`}
document.getElementById("open").onchange=render;
const COLS=["case_id","listener_id","listener_languages","target_id","target_critical","target_result","naturalness_1to5","prosody_1to5","content_complete","meaning_preserved","artifact_flags","comment","blind_transcription","blind_before_reveal","cannot_judge","rated_at"];
const cell=v=>/[",\n\r]/.test(v=String(v??""))?`"${v.replace(/"/g,'""')}"`:v;
document.getElementById("export").onclick=()=>{const lines=[COLS.join(",")];
 for(const d of DATA){const s=S(d.id);const base={case_id:d.id,listener_id:lis.value,listener_languages:langs.value,naturalness_1to5:s.nat,prosody_1to5:s.pros,
  content_complete:s.complete,meaning_preserved:s.meaning,artifact_flags:s.artifacts.join(";"),comment:s.comment,blind_transcription:d.blind?s.heard:"",
  blind_before_reveal:d.blind?String(!!s.blindTyped):"",cannot_judge:String(!!s.skip),rated_at:s.at||""};
  for(const t of d.targets)lines.push(COLS.map(k=>cell(k==="target_id"?t.id:k==="target_critical"?t.critical:k==="target_result"?(s.targets[t.id]||""):base[k])).join(","))}
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["﻿"+lines.join("\r\n")],{type:"text/csv"}));a.download=KEY.includes("mitigation")?"tts_fixes_filled.csv":"tts_listening_filled.csv";a.click()};
function parseCSV(t){const rows=[];let row=[],c="",q=false;t=t.replace(/^﻿/,"");for(let i=0;i<t.length;i++){const ch=t[i];
 if(q){if(ch==='"'){if(t[i+1]==='"'){c+='"';i++}else q=false}else c+=ch}else if(ch==='"')q=true;else if(ch===","){row.push(c);c=""}
 else if(ch==="\n"||ch==="\r"){if(ch==="\r"&&t[i+1]==="\n")i++;row.push(c);rows.push(row);row=[];c=""}else c+=ch}if(c||row.length){row.push(c);rows.push(row)}return rows}
document.getElementById("importBtn").onclick=()=>document.getElementById("importFile").click();
document.getElementById("importFile").onchange=async e=>{const f=e.target.files[0];if(!f)return;const[h,...b]=parseCSV(await f.text());const ix=n=>h.indexOf(n);
 for(const r of b){const id=r[ix("case_id")];if(!DATA.some(d=>d.id===id))continue;const s=S(id);s.targets[r[ix("target_id")]]=r[ix("target_result")];
  Object.assign(s,{nat:r[ix("naturalness_1to5")],pros:r[ix("prosody_1to5")],complete:r[ix("content_complete")],meaning:r[ix("meaning_preserved")],
  artifacts:r[ix("artifact_flags")]?r[ix("artifact_flags")].split(";"):[],comment:r[ix("comment")],heard:r[ix("blind_transcription")],
  blindTyped:r[ix("blind_before_reveal")]==="true",revealed:true,skip:r[ix("cannot_judge")]==="true",at:r[ix("rated_at")]})}save();render()};
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
