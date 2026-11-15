"""Generate data/listening/voice_compare.html: every Timbre voice on the same sentences, side by side.

Rows = voices (model, gender, persona); columns = sentences. Each cell plays the clip and shows the measured
complete-response latency; the listener rates 1-5, ticks "numbers clear" on the number sentence, stars favourites,
and can sort by average rating or by speed. Answers autosave in the browser; Export CSV saves voice_compare_filled.csv.
"""
import csv
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import gnani_api as g  # noqa: E402  (reads saved attempts only; no API calls)

OUT = PROJECT / "data" / "listening" / "voice_compare.html"
SENTENCES = [("EN-NUM", "English numbers"), ("EN-CHAT", "English greeting"), ("HI-MIX", "Hindi + amount + OTP warning")]


def main() -> None:
    with (PROJECT / "data" / "tts_voice_bank.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    texts = {r["sentence_id"]: r["input_text"] for r in rows}
    voices = {}
    for r in rows:
        key = f"{r['model']}|{r['voice']}"
        v = voices.setdefault(key, {"key": key, "voice": r["voice"], "model": r["model"].replace("timbre-", ""),
                                    "gender": r["gender"], "persona": r["persona"], "clips": {}})
        wav = PROJECT / "results" / "tts_audio" / f"{r['case_id']}.wav"
        att = g.latest_success("tts", r["case_id"])
        if not wav.exists() or att is None:
            continue
        info = g.sf.info(wav)
        v["clips"][r["sentence_id"]] = {"src": f"../../results/tts_audio/{r['case_id']}.wav", "id": r["case_id"],
                                        "ms": round(att["latency_ms"]), "dur": round(info.duration, 2),
                                        "lang": r["language"]}
    data = {"sentences": [{"id": s, "label": l, "text": texts.get(s, "")} for s, l in SENTENCES],
            "voices": sorted(voices.values(), key=lambda v: (v["model"], v["gender"], v["voice"]))}
    OUT.write_text(TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    n = sum(len(v["clips"]) for v in data["voices"])
    print(f"wrote {OUT.relative_to(PROJECT)}: {len(data['voices'])} voices, {n} clips")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Timbre Voice Comparison</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#2f5bd3;--ok:#1f7a45;--okbg:#e5f4ea;--star:#c98a00;--head:#efeee9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--text:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7f9cf5;--ok:#7fd39b;--okbg:#1d3326;--star:#f2c14e;--head:#2a2926}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px}
.bar{max-width:1200px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}h1{font-size:18px;margin:0 10px 0 0}
button,select,input[type=text]{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:6px;padding:4px 9px}
button{cursor:pointer}button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
main{max-width:1200px;margin:0 auto;padding:14px 16px}.help{color:var(--muted);font-size:13px;margin:0 0 10px}
.sent{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));gap:8px;margin-bottom:12px}
.sent div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px}.sent b{display:block;font-size:12px;color:var(--muted)}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%;min-width:880px}th,td{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}
th{background:var(--head);font-size:12px;color:var(--muted);position:sticky;top:0}
tr.fav td{background:var(--okbg)}.name{font-weight:650;font-size:15px}.tag{font-size:12px;color:var(--muted)}
audio{width:200px;height:32px;display:block;margin-bottom:4px}.stars button{width:28px;padding:2px 0;font-size:12px}
.stars .on{background:var(--accent);color:#fff;border-color:var(--accent)}.favbtn{font-size:18px;border:none;background:none;color:var(--muted);padding:0}
.favbtn.on{color:var(--star)}.avg{font-size:18px;font-weight:650}.na{color:var(--muted);font-size:12px}
input.note{width:100%;margin-top:6px;font-size:12px}label.chk{font-size:12px;color:var(--muted);display:block;margin-top:4px}
</style></head><body>
<header><div class="bar"><h1>Timbre voice comparison</h1>
<label class="tag">model <select id="fModel"><option value="">all</option><option>v3.0</option><option>v2.5</option></select></label>
<label class="tag">gender <select id="fGender"><option value="">all</option><option>Female</option><option>Male</option></select></label>
<label class="tag">sort <select id="sort"><option value="rating">my rating (high first)</option><option value="speed">fastest first</option><option value="name">model, name</option></select></label>
<label class="tag"><input type="checkbox" id="favOnly"> favourites only</label>
<span class="tag" id="count"></span>
<button class="primary" id="export">Export CSV</button></div></header>
<main><p class="help">Same sentences on every voice. v3.0 voices speak all languages; v2.5 voices are built for one language,
so they appear only in their language's column. Rate each clip 1–5 (5 = natural and clear), tick <b>numbers clear</b> when
₹1,25,450, fifteen vs fifty and 004291 are all unmistakable, and star the voices you would ship. Latency = time until the
complete audio arrived (REST, network included).</p>
<div class="sent" id="sent"></div><div class="wrap"><table id="tbl"></table></div></main>
<script>
const D=__DATA__,KEY="gnani-voice-compare-v1";
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};
const S=k=>(st[k]||={ratings:{},numbersClear:false,fav:false,note:""});
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
document.getElementById("sent").innerHTML=D.sentences.map(s=>`<div><b>${esc(s.label)}</b>${esc(s.text)}</div>`).join("");
const avg=v=>{const r=Object.values(S(v.key).ratings).map(Number).filter(Boolean);return r.length?r.reduce((a,b)=>a+b,0)/r.length:null};
const speed=v=>{const ms=Object.values(v.clips).map(c=>c.ms);return ms.length?ms.reduce((a,b)=>a+b,0)/ms.length:1e9};
function render(){const fm=fModel.value,fg=fGender.value,fo=favOnly.checked,so=sort.value;
 let vs=D.voices.filter(v=>(!fm||v.model===fm)&&(!fg||v.gender===fg)&&(!fo||S(v.key).fav));
 if(so==="rating")vs.sort((a,b)=>(avg(b)??-1)-(avg(a)??-1)||speed(a)-speed(b));
 else if(so==="speed")vs.sort((a,b)=>speed(a)-speed(b));
 else vs.sort((a,b)=>(a.model+a.voice).localeCompare(b.model+b.voice));
 const head=`<tr><th>Voice</th>${D.sentences.map(s=>`<th>${esc(s.label)}</th>`).join("")}<th>Avg</th></tr>`;
 tbl.innerHTML=head+vs.map(v=>{const s=S(v.key),a=avg(v);return `<tr class="${s.fav?"fav":""}" data-k="${esc(v.key)}">
  <td><button class="favbtn ${s.fav?"on":""}" data-fav title="favourite">★</button> <span class="name">${esc(v.voice)}</span>
   <div class="tag">Timbre ${esc(v.model)} · ${esc(v.gender)}</div><div class="tag">${esc(v.persona)}</div>
   <input type="text" class="note" data-note placeholder="note" value="${esc(s.note)}"></td>
  ${D.sentences.map(sn=>{const c=v.clips[sn.id];if(!c)return `<td class="na">not available for this voice</td>`;
   return `<td><audio controls preload="none" src="${esc(c.src)}"></audio><div class="tag">${(c.ms/1000).toFixed(2)} s · ${c.dur} s audio</div>
   <div class="stars" data-s="${sn.id}">${[1,2,3,4,5].map(n=>`<button class="${s.ratings[sn.id]==n?"on":""}">${n}</button>`).join("")}</div>
   ${sn.id==="EN-NUM"?`<label class="chk"><input type="checkbox" data-num ${s.numbersClear?"checked":""}> numbers clear</label>`:""}</td>`}).join("")}
  <td class="avg">${a?a.toFixed(1):"–"}</td></tr>`}).join("");
 tbl.querySelectorAll("tr[data-k]").forEach(tr=>{const k=tr.dataset.k,s=S(k);
  tr.querySelector("[data-fav]").onclick=()=>{s.fav=!s.fav;save();render()};
  tr.querySelector("[data-note]").oninput=e=>{s.note=e.target.value;save()};
  const n=tr.querySelector("[data-num]");if(n)n.onchange=()=>{s.numbersClear=n.checked;save()};
  tr.querySelectorAll(".stars").forEach(g=>g.querySelectorAll("button").forEach(b=>b.onclick=()=>{
   s.ratings[g.dataset.s]=s.ratings[g.dataset.s]==b.textContent?"":b.textContent;save();render()}));
  tr.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(o=>{if(o!==a)o.pause()})))});
 const rated=D.voices.filter(v=>avg(v)).length;count.textContent=`${vs.length} voices shown · ${rated} rated`}
[fModel,fGender,sort,favOnly].forEach(x=>x.onchange=render);
document.getElementById("export").onclick=()=>{const cell=v=>/[",\n\r]/.test(v=String(v??""))?`"${v.replace(/"/g,'""')}"`:v;
 const L=["model,voice,gender,persona,sentence_id,clip_id,rating_1to5,numbers_clear,favourite,latency_ms,audio_s,note"];
 for(const v of D.voices){const s=S(v.key);for(const sn of D.sentences){const c=v.clips[sn.id];if(!c)continue;
  L.push([v.model,v.voice,v.gender,v.persona,sn.id,c.id,s.ratings[sn.id]||"",sn.id==="EN-NUM"?s.numbersClear:"",s.fav,c.ms,c.dur,s.note].map(cell).join(","))}}
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["﻿"+L.join("\r\n")],{type:"text/csv"}));a.download="voice_compare_filled.csv";a.click()};
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
