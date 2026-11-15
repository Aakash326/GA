"""Generate data/listening/tts_targets_review.html from data/tts_cases.csv.

Reviewer approves or flags each prompt's drafted targets BEFORE any audio is generated.
Export -> data/listening/tts_targets_review_filled.csv, then run scripts/apply_tts_review.py.
"""
import csv
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "data" / "listening" / "tts_targets_review.html"


def main() -> None:
    with (PROJECT / "data" / "tts_cases.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    data = [{"id": r["case_id"], "category": r["category"], "language": r["language"], "text": r["input_text"],
             "paired": r["paired_with"], "targets": json.loads(r["expected_targets_json"] or "[]"),
             "variants": json.loads(r["accepted_variants_json"] or "{}"), "status": r["prompt_status"]} for r in rows]
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(PROJECT)} with {len(data)} prompts")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TTS Target Review</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#2f5bd3;--ok:#1f7a45;--okbg:#e5f4ea;--bad:#b4371f;--badbg:#fbe9e5;--chip:#efeee9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--text:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7f9cf5;--ok:#7fd39b;--okbg:#1d3326;--bad:#f19a85;--badbg:#3a221c;--chip:#2b2a27}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}
.bar{max-width:980px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}h1{font-size:18px;margin:0 12px 0 0}
.count{color:var(--muted)}button,select{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:6px;padding:5px 10px;cursor:pointer}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}main{max-width:980px;margin:0 auto;padding:16px}
.help{color:var(--muted);font-size:13px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px}
.card.ok{border-left:5px solid var(--ok)}.card.flag{border-left:5px solid var(--bad)}
.id{font-weight:650;font-family:ui-monospace,Consolas,monospace}.tag{font-size:12px;color:var(--muted)}
.text{font-size:17px;margin:6px 0 8px;padding:8px 10px;background:var(--bg);border-radius:6px;word-break:break-word}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;vertical-align:top;padding:5px 6px;border-top:1px solid var(--line)}
th{color:var(--muted);font-weight:600}.crit{font-size:11px;padding:1px 6px;border-radius:9px;background:var(--badbg);color:var(--bad)}
.minor{font-size:11px;padding:1px 6px;border-radius:9px;background:var(--chip);color:var(--muted)}
ul{margin:0;padding-left:16px}.acc li{color:var(--ok)}.rej li{color:var(--bad)}
.actions{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}.sel-ok{background:var(--okbg);border-color:var(--ok);color:var(--ok)}
.sel-flag{background:var(--badbg);border-color:var(--bad);color:var(--bad)}
textarea{width:100%;font:inherit;border:1px solid var(--line);border-radius:6px;padding:6px 8px;background:var(--bg);color:var(--text);margin-top:6px}
.table-wrap{overflow-x:auto}.hide{display:none}
</style></head><body>
<header><div class="bar"><h1>TTS target review</h1><span class="count" id="count"></span>
<select id="cat"><option value="">all categories</option></select>
<label class="tag"><input type="checkbox" id="open"> only unreviewed</label>
<button id="approveAll">Approve all unreviewed shown</button>
<button class="primary" id="export">Export CSV</button></div></header>
<main><p class="help">For each prompt, check that the <b>must hear</b> line and the accepted/rejected readings match what a
correct speaker would say. These are fixed before any audio is generated, so they can't be bent to fit the output.
Approve, or flag with a note saying what to change (e.g. "also accept 'ten fifty'"). Answers autosave in this browser;
export when done and save the CSV into <code>data/listening/</code>.</p><div id="list"></div></main>
<script>
const DATA=__DATA__, KEY="gnani-tts-target-review-v1";
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cats=[...new Set(DATA.map(d=>d.category))];const sel=document.getElementById("cat");
cats.forEach(c=>sel.insertAdjacentHTML("beforeend",`<option>${esc(c)}</option>`));
function render(){const list=document.getElementById("list");list.innerHTML="";
 const cat=sel.value, only=document.getElementById("open").checked;
 for(const d of DATA){const s=st[d.id]||{};if(cat&&d.category!==cat)continue;if(only&&s.decision)continue;
  const rows=d.targets.map(t=>{const v=d.variants[t.id]||{accept:[],reject:[]};
   return `<tr><td><b>${esc(t.id)}</b> ${t.critical?'<span class="crit">critical</span>':'<span class="minor">minor</span>'}<br><span class="tag">${esc(t.written)}</span></td>
   <td>${esc(t.must_hear)}</td><td><ul class="acc">${v.accept.map(a=>`<li>${esc(a)}</li>`).join("")}</ul></td>
   <td><ul class="rej">${v.reject.map(a=>`<li>${esc(a)}</li>`).join("")}</ul></td></tr>`}).join("");
  const card=document.createElement("div");card.className="card "+(s.decision||"");card.innerHTML=`
   <div><span class="id">${esc(d.id)}</span> <span class="tag">${esc(d.category)} · language ${esc(d.language)}${d.paired?" · paired with "+esc(d.paired):""}</span></div>
   <div class="text">${esc(d.text)}</div>
   <div class="table-wrap"><table><tr><th>Target</th><th>Must hear</th><th>Accept</th><th>Not correct</th></tr>${rows}</table></div>
   <div class="actions"><button data-v="ok" class="${s.decision==="ok"?"sel-ok":""}">Approve</button>
   <button data-v="flag" class="${s.decision==="flag"?"sel-flag":""}">Needs change</button></div>
   <textarea rows="2" placeholder="What should change? (required when flagged)">${esc(s.note||"")}</textarea>`;
  card.querySelectorAll("button").forEach(b=>b.onclick=()=>{st[d.id]={...(st[d.id]||{}),decision:(st[d.id]||{}).decision===b.dataset.v?"":b.dataset.v,at:new Date().toISOString()};save();render()});
  card.querySelector("textarea").oninput=e=>{st[d.id]={...(st[d.id]||{}),note:e.target.value};save();count()};
  list.appendChild(card)}count()}
function count(){const ok=DATA.filter(d=>(st[d.id]||{}).decision==="ok").length,fl=DATA.filter(d=>(st[d.id]||{}).decision==="flag").length;
 document.getElementById("count").textContent=`${ok} approved · ${fl} flagged · ${DATA.length-ok-fl} to review`}
sel.onchange=render;document.getElementById("open").onchange=render;
document.getElementById("approveAll").onclick=()=>{const cat=sel.value;let n=0;
 for(const d of DATA){if(cat&&d.category!==cat)continue;if(!(st[d.id]||{}).decision){st[d.id]={...(st[d.id]||{}),decision:"ok",at:new Date().toISOString()};n++}}
 save();render()};
document.getElementById("export").onclick=()=>{const cell=v=>/[",\n\r]/.test(v=String(v??""))?`"${v.replace(/"/g,'""')}"`:v;
 const lines=["case_id,decision,note,reviewed_at"].concat(DATA.map(d=>{const s=st[d.id]||{};return [d.id,s.decision||"",s.note||"",s.at||""].map(cell).join(",")}));
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["﻿"+lines.join("\r\n")],{type:"text/csv"}));
 a.download="tts_targets_review_filled.csv";a.click()};
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
