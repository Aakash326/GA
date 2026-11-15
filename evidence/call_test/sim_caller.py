"""Simulated phone caller: speaks the Exotel media-stream protocol to the bot in real time.

Sends 20 ms PCM frames (silence between lines), waits until the bot has spoken and gone quiet for GAP s, then plays
the next WAV (16 kHz mono) from the folder, in name order. Saves what the caller heard to <out>/bot_leg.wav.

    call_test/.venv/Scripts/python.exe call_test/sim_caller.py results/next/call/caller_lines
"""
import argparse, asyncio, base64, json, os, sys, time, uuid, wave
from pathlib import Path

import numpy as np, websockets

RATE, FRAME, GAP = 16000, 640, 2.0
URL = os.getenv("SIM_URL", "ws://localhost:7861/ws?sample-rate=16000")   # or the public wss:// tunnel URL


async def main(folder, barge_in_after=None):
    source_files = sorted(Path(folder).glob("*.wav"))
    lines = [wave.open(str(f)).readframes(10**9) for f in sorted(Path(folder).glob("*.wav"))]
    sid, queue, heard, state = uuid.uuid4().hex, bytearray(), bytearray(), {"loud": 0.0, "spoke": False}
    playback = {"call_id":f"test-{sid[:8]}","source_folder":str(folder),"sources":[{"index":i,"wav":str(f),"sha256":__import__("hashlib").sha256(f.read_bytes()).hexdigest()} for i,f in enumerate(source_files)],"played":[],"barge_in_after_s":barge_in_after}
    manifest = Path(folder).parent / f"playback_{sid[:8]}.json"
    manifest.write_text(json.dumps(playback,indent=2))
    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps({"event": "connected"}))
        await ws.send(json.dumps({"event": "start", "stream_sid": sid, "start": {
            "stream_sid": sid, "call_sid": f"test-{sid[:8]}", "account_sid": "sim", "media_format": {"encoding": "raw/slin", "sample_rate": str(RATE)}}}))

        async def pump():                                   # a phone line never stops: speech or silence every 20 ms
            t = time.monotonic()
            while True:
                chunk = bytes(queue[:FRAME]).ljust(FRAME, b"\0"); del queue[:FRAME]
                await ws.send(json.dumps({"event": "media", "stream_sid": sid, "media": {"payload": base64.b64encode(chunk).decode()}}))
                t += 0.02; await asyncio.sleep(max(0, t - time.monotonic()))

        async def listen():
            async for raw in ws:
                m = json.loads(raw)
                if m.get("event") == "clear":
                    playback.setdefault("clear_events",[]).append({"monotonic_s":time.monotonic()})
                if m.get("event") == "media":
                    pcm = base64.b64decode(m["media"]["payload"]); heard.extend(pcm)
                    if np.abs(np.frombuffer(pcm, np.int16)).max(initial=0) > 400:
                        if not state["spoke"]:state["first_audio"]=time.monotonic()
                        state.update(loud=time.monotonic(), spoke=True)

        tasks = [asyncio.create_task(pump()), asyncio.create_task(listen())]
        for i, pcm in enumerate(lines + [None]):
            state["spoke"] = False
            wait_started=time.monotonic()
            while not (state["spoke"] and time.monotonic() - state["loud"] > GAP):     # bot spoke, then went quiet
                if time.monotonic()-wait_started>45:raise TimeoutError("No agent reply within 45 seconds")
                if barge_in_after is not None and i>0 and pcm is not None and state["spoke"] and time.monotonic()-state.get("first_audio",time.monotonic())>=barge_in_after:
                    playback.setdefault("interruptions",[]).append({"source_index":i,"queued_monotonic_s":time.monotonic()});break
                await asyncio.sleep(0.05)
                if tasks[1].done(): break
            if pcm is None or tasks[1].done(): break
            playback["played"].append({"index":i,"queued_monotonic_s":time.monotonic(),"audio_seconds":len(pcm)/2/RATE})
            manifest.write_text(json.dumps(playback,indent=2))
            print(f"caller line {i + 1}", flush=True); queue.extend(pcm)
        try: await asyncio.wait_for(tasks[1], 30)
        except Exception: pass
        tasks[0].cancel()
    manifest.write_text(json.dumps(playback,indent=2))
    out = Path(folder).parent / f"sim_bot_leg_{time.strftime('%H%M%S')}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(bytes(heard))
    print("done ->", out)


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--live",action="store_true")
    ap.add_argument("--barge-in-after",type=float)
    args=ap.parse_args()
    if args.barge_in_after is not None and args.barge_in_after<=0:ap.error("Barge-in delay must be positive")
    if not args.live:
        print(json.dumps({"mode":"dry_run","source_clips":len(list(Path(args.folder).glob("*.wav"))),"barge_in_after":args.barge_in_after,"requests_sent":0}))
    else:
        asyncio.run(main(args.folder,args.barge_in_after))
