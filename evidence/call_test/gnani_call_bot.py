"""N10: phone test of a flight customer-service agent on the Exotel /ws leg.

Standard Pipecat cascade, same turn-taking as a production agent:
  caller audio -> Gnani STT (realtime) -> user aggregator [Silero VAD + Smart Turn v3: end of turn, barge-in]
  -> Gemini (streamed) -> Gnani TTS (one request per sentence) -> Exotel
Per call, in results/next/call/<call>/:
  conversation.jsonl  one row per agent reply: what Prisma heard, the reply, and where the response time went
  turn_NN.wav         the caller's audio for that turn, so the transcript can be checked afterwards (blind)
  call.wav            both legs (left = caller, right = agent)

    call_test/.venv/Scripts/python.exe call_test/gnani_call_bot.py        (own venv: call_test/requirements.txt)
Point the Exotel Voicebot applet (or call_test/sim_caller.py) at ws(s)://<host>:7861/ws?sample-rate=16000.
"""
import asyncio, base64, json, os, time, wave
from pathlib import Path

from call_evidence import event as evidence_event, TurnEvidence
import uvicorn, websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (BotStartedSpeakingFrame, BotStoppedSpeakingFrame, InputAudioRawFrame, LLMTextFrame,
                                   StartFrame, InterruptionFrame, TranscriptionFrame, TTSAudioRawFrame, TTSSpeakFrame,
                                   UserStartedSpeakingFrame, UserStoppedSpeakingFrame, VADUserStoppedSpeakingFrame)
from pipecat.observers.base_observer import BaseObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.serializers.exotel import ExotelFrameSerializer
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
KEY, OUT = os.environ["GNANI_API_KEY"], ROOT / "results" / "next" / "call"
TTS_MODEL, TTS_VOICE = os.getenv("CALL_TTS_MODEL", "timbre-v2.5"), os.getenv("CALL_TTS_VOICE", "Kaveri")
TTS_BUFFER_S = float(os.getenv("CALL_TTS_BUFFER_S", 0))         # > 0 hides v3.0's start-up pause, at that cost
PROMPT = ("You are Asha, a phone customer-service agent for SkyKite Airways, a fictional Indian airline. You help with "
          "booking changes, cancellations and refunds, baggage, seats, check-in and flight status. This is a demo: "
          "invent plausible booking details when needed and never ask for card, bank or ID numbers. Answer in the language "
          "of the caller's last message: English if they spoke English, Hindi if they spoke Hindi. Write Hindi in "
          "Devanagari script, never in Roman letters. Keep each reply to one or "
          "two short spoken sentences, without lists, symbols or emojis. When the caller says goodbye, say goodbye.")
GREETING = "Hello, thank you for calling SkyKite Airways. This is Asha. How can I help you today?"


class GnaniSTT(FrameProcessor):
    """Streams caller audio to Prisma realtime (1,024-byte frames) and pushes each final transcript.
    The server closes a segment after 300 ms of silence (default 500), so the transcript is ready sooner.
    If the server drops the socket (seen: 1012 "service restart" mid-call), it reconnects at most once a second."""
    def __init__(self, rate, folder=None):
        self.usage_folder, self.sent_bytes = folder, 0
        super().__init__()
        self.rate, self.buf, self.ws, self.last_try, self.reconnects = rate, bytearray(), None, 0.0, 0

    async def connect(self):
        self.last_try = time.monotonic()
        try:   # indic-auto: a comma list ("en-IN,hi-IN") is refused on realtime, although the docs allow it
            self.ws = await websockets.connect("wss://api.vachana.ai/stt/v3/stream", additional_headers={
                "x-api-key-id": KEY, "model": "prisma-v3.0", "language_code": "indic-auto", "format": "transcribe",
                "x-sample-rate": str(self.rate), "x-min-silence-ms": "300", "x-idle-timeout-sec": "900"})
            self.create_task(self.read(self.ws))
        except Exception as e:
            print("STT connect failed", repr(e)[:120], flush=True)

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, StartFrame):
            await self.connect()
        elif isinstance(frame, InputAudioRawFrame):
            if self.ws is None and time.monotonic() - self.last_try > 1:
                await self.connect()
            self.buf += frame.audio
            while self.ws and len(self.buf) >= 1024:
                try:
                    await self.ws.send(bytes(self.buf[:1024]))
                    self.sent_bytes += 1024
                except Exception: self.ws = None
                del self.buf[:1024]
            del self.buf[:-1024 * 16]                                 # while disconnected keep only the last 0.5 s
        await self.push_frame(frame, direction)

    async def read(self, ws):
        try:
            async for raw in ws:
                m = json.loads(raw)
                if m.get("type") == "error": print("STT error", m, flush=True)
                if m.get("type") == "transcript" and m.get("text"):
                    await self.push_frame(TranscriptionFrame(m["text"], "caller", m.get("timestamp", ""), result=m, finalized=True))
        except Exception as e:
            print("STT socket closed", repr(e)[:120], flush=True)
        if self.ws is ws:
            self.ws, self.reconnects = None, self.reconnects + 1

    async def cleanup(self):
        if self.usage_folder:
            with (self.usage_folder / "usage.jsonl").open("a",encoding="utf8") as usage:
                usage.write(json.dumps({"kind":"asr","seconds":self.sent_bytes / 2 / self.rate})+"\n")
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
        await super().cleanup()


class GnaniTTS(TTSService):
    """Timbre over one WebSocket, one request per sentence, raw PCM at the wire rate (no resampling)."""
    def __init__(self, rate, folder=None):
        self.usage_folder, self.sent_characters = folder, 0
        super().__init__(sample_rate=rate, push_start_frame=True, push_stop_frames=True,
                         settings=TTSSettings(model=TTS_MODEL, voice=TTS_VOICE, language=None))
        self.ws = None

    async def run_tts(self, text, context_id):
        completed = False
        if self.sent_characters + len(text) > 5000:
            raise RuntimeError("Call character budget exhausted")
        self.sent_characters += len(text)
        if self.usage_folder:
            with (self.usage_folder / "usage.jsonl").open("a",encoding="utf8") as usage:
                usage.write(json.dumps({"kind":"tts","characters":len(text),"status":"dispatch_reserved"})+"\n")
        try:
            if self.ws is None or self.ws.close_code is not None:          # the server closes idle sockets: reconnect
                self.ws = await websockets.connect("wss://api.vachana.ai/api/v1/tts", additional_headers={"X-API-Key-ID": KEY})
            lang = "hi-IN" if any("ऀ" <= c <= "ॿ" for c in text) else "en-IN"
            await self.ws.send(json.dumps({"text": text, "voice": TTS_VOICE, "model": TTS_MODEL, "language": lang,
                                           "audio_config": {"sample_rate": self.sample_rate, "num_channels": 1, "sample_width": 2,
                                                            "encoding": "linear_pcm", "container": "raw"}}))
            await self.start_ttfb_metrics()
            started, held = False, bytearray()
            while True:
                try: m = json.loads(await asyncio.wait_for(self.ws.recv(), 15))
                except Exception as e:                                     # a stuck request must not freeze the call
                    print("TTS timeout/closed", repr(e)[:120], flush=True); await self.ws.close(); break
                if m.get("type") == "start": started = True
                elif started and m.get("type") == "audio" and (m.get("data") or {}).get("audio"):
                    held += base64.b64decode(m["data"]["audio"])
                    if len(held) >= TTS_BUFFER_S * self.sample_rate * 2:   # buffer 0: every chunk goes out on arrival
                        await self.stop_ttfb_metrics()
                        yield TTSAudioRawFrame(bytes(held), self.sample_rate, 1, context_id=context_id); held.clear()
                elif m.get("type") == "error":
                    print("TTS error", m, flush=True); break
                elif m.get("type") == "complete" and started:              # a complete before start is stale: skip it
                    completed = True
                    break
            if held:
                yield TTSAudioRawFrame(bytes(held), self.sample_rate, 1, context_id=context_id)
        finally:
            if not completed and self.ws is not None:
                evidence_event(self.usage_folder,"tts_cancelled",context_id=str(context_id))
                await self.ws.close()
                self.ws = None

    async def cleanup(self):
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
        await super().cleanup()


class TurnLog(BaseObserver):
    """Watches every frame. Per agent reply: what was heard and said, and times measured from the end of the caller's
    speech (VAD stop minus its 0.2 s window): turn end decided (Smart Turn), last transcript, Gemini's first words,
    Gnani's first audio, agent audio starts."""
    def __init__(self, folder, caller, rate):
        super().__init__()
        self.dir, self.caller, self.rate, self.seen = folder, caller, rate, set()
        self.evidence = TurnEvidence(folder)
        self.audio, self.mark, self.turn, self.t, self.heard, self.reply = bytearray(), 0, 0, {}, [], []

    async def on_push_frame(self, data):
        f, now = data.frame, time.monotonic()
        if f.id in self.seen: return                                  # a frame is pushed once per processor
        self.seen.add(f.id)
        if isinstance(f, (UserStartedSpeakingFrame, UserStoppedSpeakingFrame)) and data.direction != FrameDirection.DOWNSTREAM:
            return                                                    # broadcast: the upstream copy is a second frame
        event_names = [(UserStartedSpeakingFrame,"user_started"),(UserStoppedSpeakingFrame,"user_stopped"),
                       (BotStartedSpeakingFrame,"bot_started"),(BotStoppedSpeakingFrame,"bot_stopped"),(InterruptionFrame,"interruption")]
        for frame_type,name in event_names:
            if isinstance(f,frame_type):self.evidence.record(name,now)
        if isinstance(f, InputAudioRawFrame):
            self.audio += f.audio
            if len(self.audio) > self.rate * 2 * 60:                   # keep the last 60 s
                cut = len(self.audio) - self.rate * 2 * 60; del self.audio[:cut]; self.mark = max(0, self.mark - cut)
        elif isinstance(f, VADUserStoppedSpeakingFrame):
            self.speech_end = now - f.stop_secs
        elif isinstance(f, UserStartedSpeakingFrame):
            self.mark = max(0, len(self.audio) - self.rate)            # with half a second of pre-roll
        elif isinstance(f, UserStoppedSpeakingFrame):
            self.turn, self.reply = self.turn + 1, []
            self.t = {"speech_end": getattr(self, "speech_end", now), "turn_end": now, **{k: v for k, v in self.t.items() if k == "last_transcript"}}
            with wave.open(str(self.dir / f"turn_{self.turn:02d}.wav"), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.rate); w.writeframes(bytes(self.audio[self.mark:]))
        elif isinstance(f, TranscriptionFrame):
            self.heard.append(f.text); self.t["last_transcript"] = now
        elif isinstance(f, LLMTextFrame) and "turn_end" in self.t:
            self.t.setdefault("llm_first_text", now); self.reply.append(f.text)
        elif isinstance(f, TTSAudioRawFrame) and "llm_first_text" in self.t:
            self.t.setdefault("tts_first_audio", now)
        elif isinstance(f, BotStartedSpeakingFrame) and "turn_end" in self.t:
            self.t.setdefault("bot_started", now)
        elif isinstance(f, BotStoppedSpeakingFrame) and "bot_started" in self.t:
            ms = lambda k: round((self.t[k] - self.t["speech_end"]) * 1000) if k in self.t else None
            rec = {"caller": self.caller, "turn": self.turn, "caller_said": " ".join(self.heard),
                   "agent_reply": "".join(self.reply).strip(), "caller_audio": f"{self.dir.relative_to(ROOT).as_posix()}/turn_{self.turn:02d}.wav",
                   "tts_model": TTS_MODEL, "tts_voice": TTS_VOICE, "tts_buffer_s": TTS_BUFFER_S,
                   "llm_model": os.getenv("CALL_LLM_MODEL", "gemini-3.8-flash"), "via": os.getenv("CALL_VIA", "local"),
                   "turn_end_ms": ms("turn_end"), "transcript_ms": ms("last_transcript"), "llm_first_text_ms": ms("llm_first_text"),
                   "tts_first_audio_ms": ms("tts_first_audio"), "response_ms": ms("bot_started")}
            with (self.dir / "conversation.jsonl").open("a", encoding="utf-8") as fh: fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.t, self.heard = {}, []


app = FastAPI()


@app.websocket("/ws")
async def exotel(websocket: WebSocket):
    if os.getenv("GNANI_LIVE") != "1":
        await websocket.close(code=1008, reason="Live calling disabled"); return
    token = os.getenv("CALL_ACCESS_TOKEN", "")
    if not token or websocket.query_params.get("token") != token:
        await websocket.close(code=1008, reason="Call access token required"); return
    import sys
    sys.path.insert(0,str(ROOT))
    from budget_guard import reserve_fixed
    try:
        reservation_id=reserve_fixed(ROOT,15,prior_override=os.getenv("CALL_SPENT_TO_DATE_INR"))
    except (RuntimeError, ValueError):
        await websocket.close(code=1008,reason="Reconcile Gnani spend and check the INR 500 planning ceiling"); return
    await websocket.accept()
    rate = int(websocket.query_params.get("sample-rate") or 16000)
    if rate not in (8000,16000):
        await websocket.close(code=1008,reason="Use 8000 or 16000 Hz"); return
    _, call = await parse_telephony_websocket(websocket)
    folder = OUT / (time.strftime("%Y%m%d-%H%M%S_") + str(call["call_id"])[-8:]); folder.mkdir(parents=True, exist_ok=True)
    scenario_id = websocket.query_params.get("scenario", "unspecified")
    caller = "simulated" if str(call["call_id"]).startswith("test-") else "phone"
    (folder / "call_metadata.json").write_text(json.dumps({"call_id":call["call_id"],"scenario_id":scenario_id,"caller":caller,
        "sample_rate_hz":rate,"tts_model":TTS_MODEL,"tts_voice":TTS_VOICE,"tts_buffer_s":TTS_BUFFER_S,
        "reservation_id":reservation_id,"instrumentation":"post_fix_v1","created_at_utc":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},indent=2))
    evidence_event(folder,"call_connected")
    print("Call evidence:",folder,flush=True)
    transport = FastAPIWebsocketTransport(websocket, FastAPIWebsocketParams(
        audio_in_enabled=True, audio_out_enabled=True, audio_in_sample_rate=rate, audio_out_sample_rate=rate,
        add_wav_header=False, serializer=ExotelFrameSerializer(call["stream_id"], call["call_id"],
                                                               ExotelFrameSerializer.InputParams(exotel_sample_rate=rate))))
    context = LLMContext([{"role": "assistant", "content": GREETING}])
    agg = LLMContextAggregatorPair(context, user_params=LLMUserAggregatorParams(       # turn-taking, as in production
        vad_analyzer=SileroVADAnalyzer(params=VADParams(confidence=0.7, start_secs=0.2, stop_secs=0.2, min_volume=0.6)),
        user_turn_strategies=UserTurnStrategies(stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())])))
    llm = GoogleLLMService(api_key=os.environ["GEMINI_API_KEY"], settings=GoogleLLMService.Settings(
        model=os.getenv("CALL_LLM_MODEL", "gemini-3.8-flash"), system_instruction=PROMPT, temperature=0.4,
        thinking=GoogleLLMService.ThinkingConfig(thinking_level=os.getenv("CALL_LLM_THINKING", "low"))))
    rec = AudioBufferProcessor(sample_rate=rate, num_channels=2)

    @rec.event_handler("on_audio_data")
    async def save(_, audio, sr, ch):
        with wave.open(str(folder / "call.wav"), "wb") as w:
            w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr); w.writeframes(audio)

    caller = "simulated" if str(call["call_id"]).startswith("test-") else "phone"
    task = PipelineTask(Pipeline([transport.input(), GnaniSTT(rate, folder), agg.user(), llm, GnaniTTS(rate, folder), transport.output(),
                                  rec, agg.assistant()]),
                        params=PipelineParams(audio_in_sample_rate=rate, audio_out_sample_rate=rate),
                        observers=[TurnLog(folder, caller, rate)])

    @transport.event_handler("on_client_connected")
    async def _(t, c):
        await rec.start_recording()
        await task.queue_frames([TTSSpeakFrame(GREETING)])

    @transport.event_handler("on_client_disconnected")
    async def _(t, c): await task.cancel()
    try:
        await asyncio.wait_for(PipelineRunner(handle_sigint=False).run(task), min(300.0,float(os.getenv("CALL_MAX_SECONDS", "300"))))
    except asyncio.TimeoutError:
        evidence_event(folder,"call_timeout")
        await task.cancel()
    finally:
        evidence_event(folder,"call_finished")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("CALL_BOT_PORT", 7861)))
