"""Generate data/listening/listen.html from data/asr_manifest.csv.

Open the page by double-clicking it (no server needed). It plays the local clips,
autosaves answers in the browser, and exports asr_reference_check_filled.csv,
which you save into data/listening/.
"""
import csv
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "data" / "listening" / "listen.html"

KIND_BY_CATEGORY = {
    "real_telephony": "transcribe",
    "no_speech": "nospeech",
    "synthetic_noise": "derived",
    "telephony_sim": "derived",
    "pause": "derived",
}


def main() -> None:
    with (PROJECT / "data" / "asr_manifest.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    clips = []
    for r in rows:
        kind = KIND_BY_CATEGORY.get(r["category"], "verify")
        clips.append({
            "id": r["clip_id"], "category": r["category"], "kind": kind, "language": r["language"],
            "src": "../" + r["input_path"].removeprefix("data/"), "duration": r["duration_s"],
            "reference": r["reference_transcript"], "note": r["notes"], "source": r["source_id"],
        })
    html = TEMPLATE.replace("__CLIPS__", json.dumps(clips, ensure_ascii=False).replace("</", "<\\/"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(PROJECT)} with {len(clips)} clips")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASR Reference Check</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#2f5bd3;
--ok:#1f7a45;--okbg:#e5f4ea;--bad:#b4371f;--badbg:#fbe9e5;--skip:#7a6a1f;--skipbg:#f6f0d8;--focus:#ffd76a}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--text:#ecebe6;
--muted:#a3a29b;--line:#34332f;--accent:#7f9cf5;--ok:#7fd39b;--okbg:#1d3326;--bad:#f19a85;--badbg:#3a221c;
--skip:#e3cf7a;--skipbg:#38321a;--focus:#8a6d10}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}
.bar{max-width:920px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center}
h1{font-size:18px;margin:0 12px 0 0}
.progress{flex:1;min-width:160px;height:8px;background:var(--line);border-radius:4px;overflow:hidden}
.progress>div{height:100%;background:var(--accent);width:0}
.count{color:var(--muted);font-variant-numeric:tabular-nums}
button,select{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:6px;padding:5px 10px;cursor:pointer}
button:hover{border-color:var(--accent)}
button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
main{max-width:920px;margin:0 auto;padding:16px}
.help{color:var(--muted);font-size:13px;margin:0 0 14px}
kbd{border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:0 4px;font-size:12px}
h2{font-size:15px;margin:22px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px;scroll-margin-top:90px}
.card.active{outline:3px solid var(--focus)}
.card.done-match,.card.done-ok{border-left:5px solid var(--ok)}
.card.done-mismatch,.card.done-problem,.card.done-speech{border-left:5px solid var(--bad)}
.card.done-skip{border-left:5px solid var(--skip)}
.top{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:baseline}
.id{font-weight:650;font-family:ui-monospace,Consolas,monospace}
.tag{font-size:12px;color:var(--muted)}
audio{width:100%;margin:8px 0 4px;height:36px}
.ref{font-size:17px;padding:8px 10px;background:var(--bg);border-radius:6px;margin:6px 0;word-break:break-word}
.ref.hidden{color:var(--muted);font-style:italic;font-size:14px}
.note{font-size:12px;color:var(--muted)}
.actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.actions button.sel-match,.actions button.sel-ok,.actions button.sel-silent{background:var(--okbg);border-color:var(--ok);color:var(--ok)}
.actions button.sel-mismatch,.actions button.sel-problem,.actions button.sel-speech{background:var(--badbg);border-color:var(--bad);color:var(--bad)}
.actions button.sel-skip{background:var(--skipbg);border-color:var(--skip);color:var(--skip)}
textarea,input[type=text]{width:100%;font:inherit;font-size:16px;border:1px solid var(--line);border-radius:6px;padding:6px 8px;background:var(--bg);color:var(--text);margin-top:6px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:6px}
.row label{font-size:13px;color:var(--muted)}
.hide{display:none}
#toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--text);color:var(--bg);padding:8px 14px;border-radius:6px;opacity:0;transition:opacity .2s}
#toast.show{opacity:1}
</style>
</head>
<body>
<header><div class="bar">
  <h1>ASR reference check</h1>
  <div class="progress"><div id="prog"></div></div>
  <span class="count" id="count"></span>
  <label class="tag"><input type="checkbox" id="onlyOpen"> only unfinished</label>
  <label class="tag">listener <input type="text" id="listener" style="width:90px;margin:0;font-size:14px" placeholder="R1"></label>
  <button class="primary" id="export">Export CSV</button>
  <button id="importBtn">Import CSV</button><input type="file" id="importFile" accept=".csv" class="hide">
</div></header>
<main>
<p class="help">Play each clip before judging. The dataset transcript appears after you start playback.
Judge the <b>words spoken</b> only; ignore punctuation and capitalisation.
Keys: <kbd>Space</kbd> play/pause, <kbd>R</kbd> replay, <kbd>1</kbd> matches / OK / no speech, <kbd>2</kbd> doesn't match / problem / speech,
<kbd>3</kbd> can't judge, <kbd>J</kbd>/<kbd>K</kbd> next/previous. Answers autosave in this browser; export the CSV when done
and save it into <code>data/listening/</code>.</p>
<div id="list"></div>
</main>
<div id="toast"></div>
<script>
const CLIPS = __CLIPS__;
const KEY = "gnani-asr-reference-check-v1";
const GROUPS = [
  ["verify", "Dataset clips: does the transcript match what you hear?"],
  ["transcribe", "Test-call clips: write exactly what is said"],
  ["nospeech", "No-speech controls: is any intelligible speech audible?"],
  ["derived", "Derived audio: audible, no distortion beyond the intended effect?"],
];
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { state = {}; }
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };
const s = id => (state[id] ||= {status: "", heard: "", lang: "", note: "", played: false});
let active = 0;

function esc(t){return String(t ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}

function buttons(kind){
  if (kind === "verify") return [["match","1 Matches"],["mismatch","2 Doesn't match"],["skip","3 Can't judge"]];
  if (kind === "transcribe") return [["ok","1 Transcribed"],["problem","2 Unusable audio"],["skip","3 Can't judge"]];
  if (kind === "nospeech") return [["silent","1 No speech"],["speech","2 Speech audible"],["skip","3 Can't judge"]];
  return [["ok","1 Sounds OK"],["problem","2 Problem"],["skip","3 Can't judge"]];
}

function render(){
  const list = document.getElementById("list");
  list.innerHTML = "";
  let idx = 0;
  for (const [kind, title] of GROUPS) {
    const items = CLIPS.filter(c => c.kind === kind);
    if (!items.length) continue;
    const h = document.createElement("h2"); h.textContent = `${title} (${items.length})`; list.appendChild(h);
    for (const c of items) {
      c.index = idx++;
      const st = s(c.id);
      const card = document.createElement("div");
      card.className = "card"; card.id = "card-" + c.id; card.dataset.index = c.index;
      const showRef = st.played || kind !== "verify";
      card.innerHTML = `
        <div class="top"><span class="id">${esc(c.id)}</span>
          <span class="tag">${esc(c.category)} · ${esc(c.language || "language unknown")} · ${esc(c.duration)} s${c.source && c.source !== c.id ? " · from " + esc(c.source) : ""}</span></div>
        <audio controls preload="none" src="${esc(c.src)}"></audio>
        ${kind === "verify" ? `<div class="ref ${showRef ? "" : "hidden"}" data-ref>${showRef ? esc(c.reference) : "Play the clip to reveal the dataset transcript"}</div>` : ""}
        ${kind === "derived" && c.reference ? `<div class="ref">${esc(c.reference)}</div>` : ""}
        ${c.note ? `<div class="note">${esc(c.note)}</div>` : ""}
        <div class="actions">${buttons(kind).map(([v,l]) => `<button data-v="${v}" class="${st.status===v?"sel-"+v:""}">${l}</button>`).join("")}</div>
        <div class="${kind==="transcribe" || (kind==="verify" && st.status==="mismatch") ? "" : "hide"}" data-heardwrap>
          <textarea rows="2" data-heard placeholder="${kind==="transcribe" ? "Exactly what was said (native script for Hindi/Telugu words; English words in Latin)" : "Corrected transcript: what was actually said"}">${esc(st.heard)}</textarea>
        </div>
        ${kind==="transcribe" ? `<div class="row"><label>Language heard</label>
          <select data-lang>${["","English","Hindi","Hinglish (code-mixed)","Telugu","Telugu-English mix","Other"].map(o=>`<option ${st.lang===o?"selected":""}>${o}</option>`).join("")}</select></div>` : ""}
        <input type="text" data-note placeholder="Optional note (noise, mumbling, timestamp of a problem...)" value="${esc(st.note)}">`;
      wire(card, c);
      list.appendChild(card);
    }
  }
  applyFilter(); progress(); setActive(Math.min(active, CLIPS.length - 1), false);
}

function wire(card, c){
  const st = s(c.id);
  const audio = card.querySelector("audio");
  audio.addEventListener("play", () => {
    document.querySelectorAll("audio").forEach(a => { if (a !== audio) a.pause(); });
    setActive(c.index, false);
    if (!st.played) { st.played = true; save();
      const ref = card.querySelector("[data-ref]"); if (ref) { ref.classList.remove("hidden"); ref.textContent = c.reference; } }
  });
  audio.addEventListener("error", () => toast(`Cannot load ${c.src}. Keep listen.html inside data/listening/.`));
  card.querySelectorAll(".actions button").forEach(b => b.addEventListener("click", () => choose(c, b.dataset.v)));
  const heard = card.querySelector("[data-heard]");
  if (heard) heard.addEventListener("input", () => { st.heard = heard.value; st.at = new Date().toISOString(); save(); progress(); });
  const lang = card.querySelector("[data-lang]");
  if (lang) lang.addEventListener("change", () => { st.lang = lang.value; save(); progress(); applyFilter(); });
  const note = card.querySelector("[data-note]");
  note.addEventListener("input", () => { st.note = note.value; save(); });
  card.addEventListener("click", () => setActive(c.index, false));
}

function choose(c, v){
  const st = s(c.id);
  if (c.kind === "verify" && !st.played) { toast("Play the clip first"); return; }
  st.status = st.status === v ? "" : v; st.at = new Date().toISOString();
  if (c.kind === "verify" && st.status === "mismatch" && !st.heard) st.heard = c.reference;
  save();
  const card = document.getElementById("card-" + c.id);
  card.querySelectorAll(".actions button").forEach(b => b.className = st.status === b.dataset.v ? "sel-" + b.dataset.v : "");
  const wrap = card.querySelector("[data-heardwrap]");
  if (c.kind === "verify") {
    wrap.classList.toggle("hide", st.status !== "mismatch");
    if (st.status === "mismatch") { const t = wrap.querySelector("textarea"); t.value = st.heard; t.focus(); }
  }
  progress(); applyFilter();
}

function complete(c){
  const st = s(c.id);
  if (!st.status) return false;
  if (c.kind === "transcribe" && st.status === "ok") return st.heard.trim() !== "" && st.lang !== "";
  if (c.kind === "verify" && st.status === "mismatch") return st.heard.trim() !== "";
  return true;
}

function progress(){
  const done = CLIPS.filter(complete).length;
  document.getElementById("prog").style.width = (100 * done / CLIPS.length) + "%";
  document.getElementById("count").textContent = `${done} / ${CLIPS.length} done`;
  for (const c of CLIPS) {
    const card = document.getElementById("card-" + c.id); if (!card) continue;
    card.classList.remove("done-match","done-mismatch","done-ok","done-problem","done-skip","done-silent","done-speech");
    if (complete(c)) card.classList.add("done-" + (s(c.id).status === "silent" ? "ok" : s(c.id).status));
  }
}

function applyFilter(){
  const only = document.getElementById("onlyOpen").checked;
  for (const c of CLIPS) {
    const card = document.getElementById("card-" + c.id);
    if (card) card.classList.toggle("hide", only && complete(c) && c.index !== active);
  }
}

function visible(){ return CLIPS.filter(c => !document.getElementById("card-" + c.id).classList.contains("hide")); }
function setActive(i, scroll = true){
  active = i;
  document.querySelectorAll(".card").forEach(el => el.classList.toggle("active", Number(el.dataset.index) === i));
  if (scroll) document.querySelector(`.card[data-index="${i}"]`)?.scrollIntoView({block: "center", behavior: "smooth"});
}
function step(d){
  const vis = visible(); if (!vis.length) return;
  let pos = vis.findIndex(c => c.index === active);
  pos = pos < 0 ? 0 : Math.max(0, Math.min(vis.length - 1, pos + d));
  setActive(vis[pos].index);
}

document.addEventListener("keydown", e => {
  if (e.target.matches("textarea, input, select")) { if (e.key === "Escape") e.target.blur(); return; }
  const c = CLIPS[active]; if (!c) return;
  const audio = document.querySelector(`#card-${CSS.escape(c.id)} audio`);
  if (e.key === " ") { e.preventDefault(); audio.paused ? audio.play() : audio.pause(); }
  else if (e.key === "r" || e.key === "R") { audio.currentTime = 0; audio.play(); }
  else if (["1","2","3"].includes(e.key)) choose(c, buttons(c.kind)[Number(e.key) - 1][0]);
  else if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); step(1); }
  else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); step(-1); }
});

const COLS = ["clip_id","category","kind","language","input_path","dataset_reference","status","heard_transcript","language_heard","listener_note","listener_id","listened_at"];
const csvCell = v => /[",\n\r]/.test(v = String(v ?? "")) ? `"${v.replace(/"/g,'""')}"` : v;
document.getElementById("export").addEventListener("click", () => {
  const listener = document.getElementById("listener").value.trim();
  const lines = [COLS.join(",")];
  for (const c of CLIPS) {
    const st = s(c.id);
    lines.push([c.id, c.category, c.kind, c.language, "data/" + c.src.replace("../",""), c.reference, st.status,
      st.heard, st.lang, st.note, listener, st.at || ""].map(csvCell).join(","));
  }
  const blob = new Blob(["﻿" + lines.join("\r\n")], {type: "text/csv;charset=utf-8"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = "asr_reference_check_filled.csv"; a.click(); URL.revokeObjectURL(a.href);
  const open = CLIPS.length - CLIPS.filter(complete).length;
  toast(open ? `Exported (${open} still unfinished)` : "Exported all clips");
});

function parseCSV(text){
  const rows = []; let row = [], cell = "", q = false;
  text = text.replace(/^﻿/, "");
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) { if (ch === '"') { if (text[i+1] === '"') { cell += '"'; i++; } else q = false; } else cell += ch; }
    else if (ch === '"') q = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") { if (ch === "\r" && text[i+1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
    else cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}
document.getElementById("importBtn").addEventListener("click", () => document.getElementById("importFile").click());
document.getElementById("importFile").addEventListener("change", async e => {
  const f = e.target.files[0]; if (!f) return;
  const [head, ...body] = parseCSV(await f.text());
  const ix = n => head.indexOf(n);
  let n = 0;
  for (const r of body) {
    const id = r[ix("clip_id")]; if (!CLIPS.some(c => c.id === id)) continue;
    state[id] = {status: r[ix("status")] || "", heard: r[ix("heard_transcript")] || "", lang: r[ix("language_heard")] || "",
                 note: r[ix("listener_note")] || "", played: true, at: r[ix("listened_at")] || ""};
    if (r[ix("listener_id")]) document.getElementById("listener").value = r[ix("listener_id")];
    n++;
  }
  save(); render(); toast(`Imported ${n} rows`);
});
document.getElementById("onlyOpen").addEventListener("change", applyFilter);
const lis = document.getElementById("listener");
try { lis.value = localStorage.getItem(KEY + "-listener") || ""; } catch (e) {}
lis.addEventListener("input", () => { try { localStorage.setItem(KEY + "-listener", lis.value); } catch (e) {} });
function toast(t){ const el = document.getElementById("toast"); el.textContent = t; el.classList.add("show"); clearTimeout(toast.h); toast.h = setTimeout(() => el.classList.remove("show"), 2200); }
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
