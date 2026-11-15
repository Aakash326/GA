"""Generate data/listening/reference_review.html: the items the Gemini judge could not settle (no API calls).

Sections
  calls    - the 15 real call clips: Gemini's blind transcript is a draft; the listener confirms or corrects it.
             (Prisma output is never shown.)
  flagged  - one row per SOURCE clip whose dataset reference the judge disputed (derived noise/phone/pause copies
             inherit the decision). Listener picks dataset / judge / edits.
  nospeech - no-speech controls where the judge heard something.
Export: reference_review_filled.csv -> scripts/apply_reference_review.py
"""
import csv
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
PAGE = PROJECT / "data" / "listening" / "reference_review.html"


def read(path):
    with (PROJECT / path).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    man = {r["clip_id"]: r for r in read("data/asr_manifest.csv")}
    judge = read("results/judge/asr_judge.csv")

    def root(cid):
        seen = set()
        while man[cid]["source_id"] and man[cid]["source_id"] != cid and cid not in seen:
            seen.add(cid)
            cid = man[cid]["source_id"]
        return cid

    by_root, items = {}, []
    for j in judge:
        if j["task"] == "draft_reference":
            items.append({"kind": "call", "id": j["clip_id"], "src": "../" + man[j["clip_id"]]["input_path"].removeprefix("data/"),
                          "draft": j["judge_blind"], "judge_language": j["judge_language"]})
        elif j["status"].endswith("human check") and j["task"] == "verify_reference":
            by_root.setdefault(root(j["clip_id"]), []).append(j)
        elif j["status"].endswith("human check") and j["task"] == "no_speech_check":
            items.append({"kind": "nospeech", "id": j["clip_id"], "src": "../" + man[j["clip_id"]]["input_path"].removeprefix("data/"),
                          "draft": j["judge_blind"]})
    jmap = {j["clip_id"]: j for j in judge}
    for rid, js in sorted(by_root.items()):
        show = rid if rid in jmap else js[0]["clip_id"]  # listen to the clean source when the judge checked it
        j = jmap.get(show, js[0])
        derived = sorted({c for c, r in man.items() if c != rid and root(c) == rid})
        items.append({"kind": "flagged", "id": rid, "src": "../" + man[show]["input_path"].removeprefix("data/"),
                      "language": man[rid]["language"], "reference": man[rid]["reference_transcript"], "draft": j["judge_blind"],
                      "differences": json.loads(j["differences"] or "[]"), "flagged_clips": [x["clip_id"] for x in js],
                      "derived": derived, "category": man[rid]["category"]})
    PAGE.write_text(TEMPLATE.replace("__DATA__", json.dumps(items, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    kinds = {}
    for i in items:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    print(f"wrote {PAGE.relative_to(PROJECT)}: {kinds}")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reference Review</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#2f5bd3;--ok:#1f7a45;--okbg:#e5f4ea;--bad:#b4371f;--badbg:#fbe9e5;--mark:#fff1b8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--text:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7f9cf5;--ok:#7fd39b;--okbg:#1d3326;--bad:#f19a85;--badbg:#3a221c;--mark:#5a4a12}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px}
.bar{max-width:900px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}h1{font-size:18px;margin:0 10px 0 0}
button,select{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:6px;padding:4px 10px;cursor:pointer}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}main{max-width:900px;margin:0 auto;padding:16px}
h2{font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin:22px 0 8px}.help{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px}.card.done{border-left:5px solid var(--ok)}
.id{font-weight:650;font-family:ui-monospace,Consolas,monospace}.tag{font-size:12px;color:var(--muted)}audio{width:100%;height:36px;margin:6px 0}
.row{display:grid;grid-template-columns:110px 1fr;gap:4px 10px;margin:4px 0}.lab{font-size:12px;color:var(--muted);padding-top:3px}
.txt{font-size:17px;word-break:break-word}mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 2px}
.actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.on{background:var(--okbg);border-color:var(--ok);color:var(--ok)}
textarea{width:100%;font:inherit;font-size:16px;border:1px solid var(--line);border-radius:6px;padding:6px 8px;background:var(--bg);color:var(--text);margin-top:6px}
.hide{display:none}@media (max-width:560px){.row{grid-template-columns:1fr}}
</style></head><body>
<header><div class="bar"><h1>Reference review</h1><span class="tag" id="count"></span><button class="primary" id="export">Export CSV</button></div></header>
<main><p class="help">Only the clips the Gemini judge could not settle. Listen, then choose. For flagged clips, highlighted words are
where the dataset text and Gemini differ; your choice also applies to that clip's noisy/phone/pause copies.
For call clips, correct Gemini's draft to exactly what is said (Hindi in Devanagari, English words in Latin letters).</p>
<div id="list"></div></main>
<script>
const D=__DATA__,KEY="gnani-reference-review-v1";let st={};try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const hl=(text,words)=>{let h=esc(text);for(const w of words.filter(Boolean).sort((a,b)=>b.length-a.length)){h=h.split(esc(w)).join(`<mark>${esc(w)}</mark>`)}return h};
const S=id=>(st[id]||={choice:"",text:"",lang:""});
const done=d=>{const s=S(d.id);return d.kind==="call"?(s.choice==="unusable"||(s.choice==="ok"&&s.text.trim()&&s.lang)):!!s.choice&&(s.choice!=="edit"||s.text.trim())};
function render(){const L=document.getElementById("list");L.innerHTML="";
 for(const [kind,title] of [["call","Call clips: confirm Gemini's draft"],["flagged","Flagged dataset references"],["nospeech","No-speech controls"]]){
  const its=D.filter(d=>d.kind===kind);if(!its.length)continue;L.insertAdjacentHTML("beforeend",`<h2>${title} (${its.length})</h2>`);
  for(const d of its){const s=S(d.id);if(kind==="call"&&!s.text)s.text=d.draft;const c=document.createElement("div");c.className="card"+(done(d)?" done":"");
   let body="";
   if(kind==="call")body=`<div class="row"><span class="lab">Gemini draft</span><span class="txt">${esc(d.draft)||"(empty)"}</span></div>
     <textarea rows="2" data-t>${esc(s.text)}</textarea>
     <div class="actions"><select data-l>${["","English","Hindi","Hinglish (code-mixed)","Telugu","Other"].map(o=>`<option ${s.lang===o?"selected":""}>${o}</option>`).join("")}</select>
     <button data-c="ok" class="${s.choice==="ok"?"on":""}">Confirmed / corrected</button><button data-c="unusable" class="${s.choice==="unusable"?"on":""}">Unusable audio</button></div>`;
   if(kind==="flagged"){const refW=d.differences.map(x=>x.reference),hW=d.differences.map(x=>x.heard);
    body=`<div class="row"><span class="lab">Dataset text</span><span class="txt">${hl(d.reference,refW)}</span></div>
     <div class="row"><span class="lab">Gemini heard</span><span class="txt">${hl(d.draft,hW)}</span></div>
     <div class="tag">applies to: ${esc([d.id,...d.derived].join(", "))}</div>
     <div class="actions"><button data-c="dataset" class="${s.choice==="dataset"?"on":""}">Dataset text is right</button>
     <button data-c="judge" class="${s.choice==="judge"?"on":""}">Gemini is right</button><button data-c="edit" class="${s.choice==="edit"?"on":""}">Neither: edit</button>
     <button data-c="skip" class="${s.choice==="skip"?"on":""}">Can't judge</button></div>
     <textarea rows="2" data-t class="${s.choice==="edit"?"":"hide"}" placeholder="What is actually said">${esc(s.text)}</textarea>`}
   if(kind==="nospeech")body=`<div class="row"><span class="lab">Gemini heard</span><span class="txt">${esc(d.draft)}</span></div>
     <div class="actions"><button data-c="silent" class="${s.choice==="silent"?"on":""}">No intelligible speech</button><button data-c="speech" class="${s.choice==="speech"?"on":""}">Speech audible</button></div>`;
   c.innerHTML=`<div><span class="id">${esc(d.id)}</span> <span class="tag">${esc(d.category||d.kind)} ${esc(d.language||"")}</span></div>
     <audio controls preload="none" src="${esc(d.src)}"></audio>${body}`;
   c.querySelectorAll("[data-c]").forEach(b=>b.onclick=()=>{s.choice=s.choice===b.dataset.c?"":b.dataset.c;if(kind==="flagged"&&s.choice==="edit"&&!s.text)s.text=d.draft;save();render()});
   const t=c.querySelector("[data-t]");if(t)t.oninput=()=>{s.text=t.value;save();count()};
   const l=c.querySelector("[data-l]");if(l)l.onchange=()=>{s.lang=l.value;save();render()};
   c.querySelector("audio").addEventListener("play",e=>document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()}));
   L.appendChild(c)}}count()}
function count(){document.getElementById("count").textContent=`${D.filter(done).length} / ${D.length} done`}
document.getElementById("export").onclick=()=>{const cell=v=>/[",\n\r]/.test(v=String(v??""))?`"${v.replace(/"/g,'""')}"`:v;
 const L=["kind,clip_id,choice,text,language_heard,dataset_reference,judge_text,applies_to"];
 for(const d of D){const s=S(d.id);L.push([d.kind,d.id,s.choice,s.text,s.lang,d.reference||"",d.draft||"",[d.id,...(d.derived||[])].join(";")].map(cell).join(","))}
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["﻿"+L.join("\r\n")],{type:"text/csv"}));a.download="reference_review_filled.csv";a.click()};
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
