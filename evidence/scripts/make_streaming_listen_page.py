"""Let a listener hear streaming latency: data/listening/streaming_listen.html (no API calls).

For each saved stream (all-voice check, round 1, plus the T23 ~20 s runs) two files are rebuilt from the recorded
chunk arrival times and the assembled audio:
  as_arrives: silence from dispatch until the first chunk, then audio played the moment each chunk arrives; if the
              next chunk is late, the gap is silence (what a caller hears if playback starts immediately).
  buffered:   silence until the stall-free start, then the whole stream without gaps.
Both start at the moment the text was sent, so the leading silence IS the wait.
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import gnani_api as g  # noqa: E402

OUT_DIR = PROJECT / "results" / "tts_audio" / "stream_as_heard"
PAGE = PROJECT / "data" / "listening" / "streaming_listen.html"


def rebuild(a):
    audio, sr = sf.read(PROJECT / a["audio_path"], dtype="float32")
    chunks = json.loads((PROJECT / a["timeline_path"]).read_text(encoding="utf-8"))["chunks"]
    out, pos, play_end = [np.zeros(int(chunks[0]["t_s"] * sr), dtype="float32")], 0, chunks[0]["t_s"]
    for c in chunks:
        n = int(round(c["dur_s"] * sr))
        if c["t_s"] > play_end:
            out.append(np.zeros(int((c["t_s"] - play_end) * sr), dtype="float32"))
            play_end = c["t_s"]
        out.append(audio[pos:pos + n])
        pos += n
        play_end += c["dur_s"]
    as_arrives = np.concatenate(out)
    buffered = np.concatenate([np.zeros(int(a["stall_free_start_ms"] / 1000 * sr), dtype="float32"), audio])
    return as_arrives, buffered, sr


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    picks = [a for a in g.attempts("tts_stream") if a.get("ok") and
             (a["run_tag"].startswith("stream_voice_") and a["run_tag"].endswith("_r1")
              or a["case_id"] == "T23" and a["run_tag"].startswith("stream_") and a["run_tag"].endswith("_r1"))]
    # SSE vs WebSocket comparison, round 1 (same time window)
    picks += [a for a in g.attempts("tts_stream") + g.attempts("tts_ws") if a.get("ok") and a["run_tag"].startswith("cmp_")
              and "_r1" in a["run_tag"]]
    items = []
    for a in picks:
        as_arr, buf, sr = rebuild(a)
        stem = f"{a['case_id']}__{a['run_tag']}"
        sf.write(OUT_DIR / f"{stem}__as_arrives.wav", as_arr, sr, subtype="PCM_16")
        sf.write(OUT_DIR / f"{stem}__buffered.wav", buf, sr, subtype="PCM_16")
        transport = "WebSocket " + ("warm" if a["run_tag"].endswith("_warm") else "cold") if a["kind"] == "tts_ws" else "SSE"
        group = "CMP-" + a["case_id"] if a["run_tag"].startswith("cmp_") else a["case_id"]
        items.append({"case": group, "transport": transport, "voice": a["settings"]["voice"], "model": a["settings"]["model"].replace("timbre-", ""),
                      "text": a["input_text"], "first_ms": round(a["ttfa_ms"]), "smooth_ms": round(a["stall_free_start_ms"]),
                      "pause_s": a["stall_s"], "audio_s": a["audio_duration_s"],
                      "as_arrives": f"../../results/tts_audio/stream_as_heard/{stem}__as_arrives.wav",
                      "buffered": f"../../results/tts_audio/stream_as_heard/{stem}__buffered.wav"})
    order = {"T31": 0, "T23": 1, "CMP-T31": 2, "CMP-T23": 3}
    items.sort(key=lambda i: (order.get(i["case"], 9), i["model"], i["voice"], i["transport"], i["smooth_ms"]))
    PAGE.write_text(TEMPLATE.replace("__DATA__", json.dumps(items, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
    print(f"wrote {PAGE.relative_to(PROJECT)} with {len(items)} streams; audio in {OUT_DIR.relative_to(PROJECT)}")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Streaming Latency Listening</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--text:#1d1d1b;--muted:#6b6b66;--line:#e2e1dc;--accent:#2f5bd3;--warn:#b4371f;--ok:#1f7a45;--head:#efeee9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--text:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7f9cf5;--warn:#f19a85;--ok:#7fd39b;--head:#2a2926}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:20px;margin:0 0 6px}h2{font-size:15px;margin:20px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.help{color:var(--muted);margin:0 0 10px}.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%;min-width:760px}th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:middle}
th{background:var(--head);font-size:12px;color:var(--muted)}audio{width:230px;height:32px}
.name{font-weight:650}.tag{font-size:12px;color:var(--muted)}.slow{color:var(--warn);font-weight:650}.fast{color:var(--ok);font-weight:650}
.sent{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin:0 0 8px}
</style></head><body><main>
<h1>Hear the streaming delay</h1>
<p class="help">Each clip starts at the moment the text was sent to Gnani, so the silence at the start is the real wait.
<b>Played as it arrives</b>: playback starts with the first chunk; v3.0 voices then go silent until the rest arrives.
<b>Buffered</b>: playback waits until it can run without gaps. Recorded on 13 Nov 2026 over one office connection.</p>
<div id="out"></div></main>
<script>
const D=__DATA__;const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const groups=[["T31","Short sentence on every voice (SSE, 13 Nov)"],["T23","About 20 seconds of speech (SSE, 13 Nov)"],["CMP-T31","SSE vs WebSocket, short sentence (14 Nov, same time window)"],["CMP-T23","SSE vs WebSocket, about 20 seconds (14 Nov)"]];
document.getElementById("out").innerHTML=groups.map(([cid,title])=>{const rows=D.filter(d=>d.case===cid);if(!rows.length)return"";
 return `<h2>${title}</h2><div class="sent">“${esc(rows[0].text)}”</div><div class="wrap"><table>
 <tr><th>Voice</th><th>Played as it arrives</th><th>Buffered (smooth)</th><th>First sound</th><th>Smooth speech from</th><th>Pause</th></tr>
 ${rows.map(d=>`<tr><td><span class="name">${esc(d.voice)}</span><div class="tag">Timbre ${esc(d.model)} · ${esc(d.transport)} · ${d.audio_s} s audio</div></td>
  <td><audio controls preload="none" src="${esc(d.as_arrives)}"></audio></td><td><audio controls preload="none" src="${esc(d.buffered)}"></audio></td>
  <td>${(d.first_ms/1000).toFixed(2)} s</td><td class="${d.smooth_ms>800?"slow":"fast"}">${(d.smooth_ms/1000).toFixed(2)} s</td>
  <td>${d.pause_s>0?d.pause_s.toFixed(2)+" s":"none"}</td></tr>`).join("")}</table></div>`}).join("");
document.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(o=>{if(o!==a)o.pause()})));
</script></body></html>
"""

if __name__ == "__main__":
    main()
