"""Build the ASR test set from public datasets plus the team's own test-call clips.

Run from the project folder:
    .venv\\Scripts\\python.exe scripts\\prepare_asr_data.py --calls-root <folder with call recordings>

What it does (idempotent; existing outputs are reused):
  1. Indexes Google SVQ metadata (en_in / hi_in / te_in) without downloading audio.
  2. Selects clips with a fixed seed BEFORE any model output is seen.
  3. Downloads only the parquet row groups that hold the selected SVQ clips.
  4. Streams FLEURS dev archives for a few longer Hindi/Telugu sentences.
  5. Downloads two MUSAN public-domain background-noise recordings.
  6. Copies a sample of real test-call turns (team voices only).
  7. Derives matched noise (20/10/0 dB SNR), telephone-channel (8 kHz PCM,
     G.711 A-law, G.711 mu-law), pause-inserted and no-speech clips.
  8. Writes data/asr_manifest.csv and regenerates data/listening/listen.html.

No Gnani API calls are made here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import soundfile as sf

PROJECT = Path(__file__).resolve().parents[1]
AUDIO = PROJECT / "data" / "audio"
CACHE = PROJECT / "data" / "sources" / "cache"
SOURCES = PROJECT / "data" / "sources"
LISTEN = PROJECT / "data" / "listening"
SEED = 20261113
TARGET_SR = 16000

SVQ_BASE = "https://huggingface.co/datasets/google/svq/resolve/main/1.0.0/audio/"
SVQ_LICENSE = "Google SVQ (CC-BY-4.0)"
FLEURS_BASE = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/"
FLEURS_LICENSE = "Google FLEURS (CC-BY-4.0)"
MUSAN_BASE = "https://huggingface.co/datasets/FluidInference/musan/resolve/main/noise/free-sound/"
MUSAN_LICENSE = "MUSAN noise/free-sound (public domain per corpus LICENSE)"
CALL_LICENSE = "Internal test call; team voices only, consent confirmed by project owner"

LANG = {"en_in": "en-IN", "hi_in": "hi-IN", "te_in": "te-IN"}
LATIN = re.compile(r"[A-Za-z]")
DIGIT = re.compile(r"\d")

MANIFEST_FIELDS = [
    "clip_id", "selected", "category", "tags", "source_id", "speaker_id", "language", "model",
    "output_mode", "sample_rate_hz", "duration_s", "noise_snr_db", "codec", "input_path",
    "source_dataset", "source_ref", "source_or_prompt", "reference_transcript",
    "reference_origin", "human_reference_verified", "is_no_speech", "expected_entities_json",
    "license_or_consent", "derivation_json", "input_sha256", "notes", "exclusion_reason",
]


# ---------------------------------------------------------------- helpers
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, samples.astype(np.float32), sr, subtype="PCM_16")


def load_mono(data, target_sr: int = TARGET_SR) -> np.ndarray:
    """Decode to mono float32 at target_sr (ffmpeg resampler when rates differ)."""
    samples, sr = sf.read(data, always_2d=True, dtype="float32")
    mono = samples.mean(axis=1)
    if sr == target_sr:
        return mono
    tmp_in, tmp_out = CACHE / "_resample_in.wav", CACHE / "_resample_out.wav"
    sf.write(tmp_in, mono, sr, subtype="FLOAT")
    ffmpeg("-i", tmp_in, "-ar", str(target_sr), "-ac", "1", "-c:a", "pcm_f32le", tmp_out)
    out, _ = sf.read(tmp_out, dtype="float32")
    return out


def ffmpeg(*args) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)]
    subprocess.run(cmd, check=True)


def frame_rms(x: np.ndarray, sr: int, frame_s: float = 0.02) -> np.ndarray:
    n = int(sr * frame_s)
    usable = len(x) // n * n
    frames = x[:usable].reshape(-1, n)
    return np.sqrt((frames ** 2).mean(axis=1) + 1e-12)


def active_mask(x: np.ndarray, sr: int, rel_db: float = -35.0, frame_s: float = 0.02) -> np.ndarray:
    """Per-sample mask of frames within rel_db of the loudest frame (simple energy VAD)."""
    rms = frame_rms(x, sr, frame_s)
    keep = 20 * np.log10(rms / rms.max()) > rel_db
    n = int(sr * frame_s)
    mask = np.zeros(len(x), dtype=bool)
    mask[: len(keep) * n] = np.repeat(keep, n)
    return mask


# ---------------------------------------------------------------- SVQ
def svq_index() -> pd.DataFrame:
    path = SOURCES / "svq_index_in.csv"
    if path.exists():
        return pd.read_csv(path)
    import fsspec
    import pyarrow.parquet as pq

    frames = []
    for loc in LANG:
        for env in ("clean", "background_speech", "media_noise", "traffic_noise"):
            name = f"utts_{loc}_{env}.parquet"
            with fsspec.open(SVQ_BASE + name, "rb", block_size=2**20) as handle:
                table = pq.ParquetFile(handle).read(
                    columns=["utt_id", "locale", "speaker_id", "speaker_age", "speaker_gender", "environment", "text"])
            df = table.to_pandas()
            df["file"], df["row"] = name, range(len(df))
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(path, index=False, encoding="utf-8")
    return df


def pick_distinct_speakers(pool: pd.DataFrame, n: int, rng: random.Random, used: set) -> list[pd.Series]:
    """One clip per speaker first (sorted speaker order, seeded clip choice), then fill."""
    pool = pool[~pool.utt_id.isin(used)]
    picks = []
    speakers = sorted(pool.speaker_id.unique())
    rng.shuffle(speakers)
    for spk in speakers:
        if len(picks) == n:
            break
        rows = pool[pool.speaker_id == spk].sort_values("utt_id")
        picks.append(rows.iloc[rng.randrange(len(rows))])
    while len(picks) < n:
        rest = pool[~pool.utt_id.isin({p.utt_id for p in picks})].sort_values("utt_id")
        picks.append(rest.iloc[rng.randrange(len(rest))])
    used.update(p.utt_id for p in picks)
    return picks


def select_svq(df: pd.DataFrame) -> dict[str, list[pd.Series]]:
    rng = random.Random(SEED)
    used: set = set()

    def env(loc, environment, digits=False, latin_ok=False):
        d = df[(df.locale == loc) & (df.environment == environment)]
        d = d[d.text.str.contains(DIGIT)] if digits else d[~d.text.str.contains(DIGIT)]
        if not latin_ok and loc != "en_in":
            d = d[~d.text.str.contains(LATIN)]
        return d

    sel = {
        "CL-EN": pick_distinct_speakers(env("en_in", "clean"), 6, rng, used),
        "CL-HI": pick_distinct_speakers(env("hi_in", "clean"), 5, rng, used),
        "CL-TE": pick_distinct_speakers(env("te_in", "clean"), 4, rng, used),
        "NUM-EN": pick_distinct_speakers(env("en_in", "clean", digits=True), 3, rng, used),
        "NUM-HI": pick_distinct_speakers(env("hi_in", "clean", digits=True), 2, rng, used),
        "RN-EN-BG": pick_distinct_speakers(env("en_in", "background_speech"), 1, rng, used),
        "RN-EN-MEDIA": pick_distinct_speakers(env("en_in", "media_noise"), 1, rng, used),
        "RN-HI-TRAFFIC": pick_distinct_speakers(env("hi_in", "traffic_noise"), 1, rng, used),
        "RN-HI-BG": pick_distinct_speakers(env("hi_in", "background_speech"), 1, rng, used),
    }
    # Telugu: same speaker + same text recorded clean and in traffic noise.
    # In SVQ 1.0.0 every such pair comes from ONE speaker, so the pairs share a voice.
    te = df[df.locale == "te_in"]
    pairs = []
    for (spk, text), grp in te.groupby(["speaker_id", "text"]):
        envs = set(grp.environment)
        if {"clean", "traffic_noise"} <= envs and not DIGIT.search(text) and not LATIN.search(text):
            pairs.append((spk, text, grp))
    pairs.sort(key=lambda p: (p[0], p[1]))
    rng.shuffle(pairs)
    sel["RNP-TE"] = [grp for _, _, grp in pairs[:3]]
    return sel


def fetch_svq_audio(rows: list[pd.Series]) -> dict[str, bytes]:
    """Read only the row groups that contain the requested rows."""
    import fsspec
    import pyarrow.parquet as pq

    out: dict[str, bytes] = {}
    by_file: dict[str, list[pd.Series]] = {}
    for r in rows:
        cached = CACHE / "svq" / f"{r.utt_id}.bin"
        if cached.exists():
            out[r.utt_id] = cached.read_bytes()
        else:
            by_file.setdefault(r.file, []).append(r)
    for name, wanted in by_file.items():
        with fsspec.open(SVQ_BASE + name, "rb", block_size=2**22) as handle:
            pf = pq.ParquetFile(handle)
            bounds, start = [], 0
            for i in range(pf.metadata.num_row_groups):
                n = pf.metadata.row_group(i).num_rows
                bounds.append((i, start, start + n))
                start += n
            for gi, lo, hi in bounds:
                need = [r for r in wanted if lo <= r.row < hi]
                if not need:
                    continue
                print(f"  downloading {name} row group {gi} for {len(need)} clip(s)")
                table = pf.read_row_group(gi, columns=["utt_id", "waveform"])
                ids = table.column("utt_id").to_pylist()
                waves = table.column("waveform").to_pylist()
                for r in need:
                    blob = waves[ids.index(r.utt_id)]["bytes"]
                    (CACHE / "svq").mkdir(parents=True, exist_ok=True)
                    (CACHE / "svq" / f"{r.utt_id}.bin").write_bytes(blob)
                    out[r.utt_id] = blob
    return out


# ---------------------------------------------------------------- FLEURS
def fleurs_long(locale: str, n: int, rng: random.Random) -> list[dict]:
    tsv = requests.get(FLEURS_BASE + f"{locale}/dev.tsv", timeout=60)
    tsv.raise_for_status()
    rows = []
    for line in tsv.text.splitlines():
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        rid, fname, raw, _norm, _phon, nsamp, gender = parts[:7]
        dur = int(nsamp) / 16000
        if 12.0 <= dur <= 25.0:
            rows.append({"id": rid, "file": fname, "text": raw, "duration": dur, "gender": gender})
    rows.sort(key=lambda r: r["file"])
    # One recording per sentence id, then seeded choice.
    seen, unique = set(), []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    picks = rng.sample(unique, n)
    missing = [p for p in picks if not (CACHE / "fleurs" / p["file"]).exists()]
    if missing:
        names = {p["file"] for p in missing}
        print(f"  streaming FLEURS {locale} dev archive for {len(names)} file(s)")
        with requests.get(FLEURS_BASE + f"{locale}/audio/dev.tar.gz", stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with tarfile.open(fileobj=resp.raw, mode="r|gz") as tar:
                for member in tar:
                    base = Path(member.name).name
                    if base in names:
                        (CACHE / "fleurs").mkdir(parents=True, exist_ok=True)
                        (CACHE / "fleurs" / base).write_bytes(tar.extractfile(member).read())
                        names.discard(base)
                        if not names:
                            break
        if names:
            raise RuntimeError(f"FLEURS files not found in archive: {names}")
    return picks


# ---------------------------------------------------------------- MUSAN
def musan_noises() -> list[tuple[str, np.ndarray]]:
    ann = requests.get(MUSAN_BASE + "ANNOTATIONS", timeout=60).text.split()
    ids = [a for a in ann if a.startswith("noise-free-sound-")]
    rng = random.Random(SEED)
    rng.shuffle(ids)
    noises = []
    for nid in ids:
        cached = CACHE / "musan" / f"{nid}.wav"
        if not cached.exists():
            resp = requests.get(MUSAN_BASE + f"{nid}.wav", timeout=120)
            resp.raise_for_status()
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(resp.content)
        x = load_mono(cached)
        if len(x) >= 12 * TARGET_SR and frame_rms(x, TARGET_SR).min() > 1e-4:
            noises.append((nid, x))
        if len(noises) == 2:
            return noises
    raise RuntimeError("Not enough suitable MUSAN background noises")


# ---------------------------------------------------------------- calls
def select_calls(root: Path, n: int) -> list[Path]:
    clips = sorted(root.glob("logs/retrieval/real_*/*/turn_*.wav")) + sorted(
        root.glob("logs/retrieval/2026*/turn_*.wav"))
    rng = random.Random(SEED)
    eligible = []
    for c in clips:
        info = sf.info(c)
        if 1.5 <= info.duration <= 8.0:
            x, sr = sf.read(c, dtype="float32")
            if np.sqrt(np.mean(x ** 2)) > 0.003:
                eligible.append(c)
    by_call: dict[Path, list[Path]] = {}
    for c in eligible:
        by_call.setdefault(c.parent, []).append(c)
    picks = []
    for call in sorted(by_call):
        group = by_call[call]
        picks.extend(rng.sample(group, min(2, len(group))))
    rng.shuffle(picks)
    return sorted(picks[:n])


# ---------------------------------------------------------------- derivations
def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> tuple[np.ndarray, dict]:
    reps = int(np.ceil(len(speech) / len(noise)))
    seg = np.tile(noise, reps)[: len(speech)]
    mask = active_mask(speech, TARGET_SR)
    speech_rms = np.sqrt(np.mean(speech[mask] ** 2))
    noise_rms = np.sqrt(np.mean(seg[mask] ** 2))
    scale = speech_rms / (noise_rms * 10 ** (snr_db / 20))
    mix = speech + scale * seg
    peak = float(np.abs(mix).max())
    gain = 0.98 / peak if peak > 0.98 else 1.0
    measured = 20 * np.log10(speech_rms / np.sqrt(np.mean((scale * seg[mask]) ** 2)))
    return mix * gain, {"noise_offset_s": 0.0, "noise_scale": float(scale), "post_gain": float(gain),
                        "measured_snr_db": round(float(measured), 2), "rms_region": "active-speech frames (-35 dB energy VAD)"}


def insert_pause(speech: np.ndarray, pause_s: float = 1.5, trail_s: float = 2.0) -> tuple[np.ndarray, dict]:
    sr = TARGET_SR
    rms = frame_rms(speech, sr)
    idx = np.flatnonzero(20 * np.log10(rms / rms.max()) > -35)
    lo, hi = idx[0] + int(0.35 * (idx[-1] - idx[0])), idx[0] + int(0.65 * (idx[-1] - idx[0]))
    gap = lo + int(np.argmin(rms[lo:hi + 1]))
    cut = gap * int(sr * 0.02) + int(sr * 0.01)
    out = np.concatenate([speech[:cut], np.zeros(int(pause_s * sr)), speech[cut:], np.zeros(int(trail_s * sr))])
    return out, {"pause_inserted_at_s": round(cut / sr, 3), "pause_s": pause_s, "trailing_silence_s": trail_s,
                 "rule": "pause placed at the lowest-energy 20 ms frame within 35-65% of the active span"}


def telephone_chain(src: Path, base: str) -> dict[str, Path]:
    """8 kHz band-limited PCM (pre-codec control), then G.711 A-law / mu-law round trips."""
    pcm = AUDIO / f"{base}-8K.wav"
    ffmpeg("-i", src, "-af", "highpass=f=300,lowpass=f=3400", "-ar", "8000", "-ac", "1", "-c:a", "pcm_s16le", pcm)
    out = {"8K": pcm}
    for codec, tag in (("pcm_alaw", "ALAW"), ("pcm_mulaw", "ULAW")):
        enc = CACHE / f"{base}-{tag}-encoded.wav"
        dec = AUDIO / f"{base}-{tag}.wav"
        ffmpeg("-i", pcm, "-c:a", codec, enc)
        ffmpeg("-i", enc, "-c:a", "pcm_s16le", dec)
        out[tag] = dec
    return out


# ---------------------------------------------------------------- main
def row(**kw) -> dict:
    base = {f: "" for f in MANIFEST_FIELDS}
    base.update(selected="true", human_reference_verified="false", is_no_speech="false")
    base.update({k: ("" if v is None else v) for k, v in kw.items()})
    path = PROJECT / base["input_path"]
    info = sf.info(path)
    base["sample_rate_hz"], base["duration_s"] = info.samplerate, round(info.duration, 3)
    base["input_sha256"] = sha256(path)
    return base


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls-root", type=Path, required=True,
                    help="commodity voice-agent repo folder containing logs/retrieval/real_* call turns")
    ap.add_argument("--n-calls", type=int, default=15)
    args = ap.parse_args()
    for d in (AUDIO, CACHE, LISTEN):
        d.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    print("1/6 SVQ index + selection")
    df = svq_index()
    sel = select_svq(df)
    flat = [r for k, v in sel.items() if k != "RNP-TE" for r in v]
    flat += [r for grp in sel["RNP-TE"] for _, r in grp[grp.environment.isin(["clean", "traffic_noise"])]
             .sort_values("environment").groupby("environment").head(1).iterrows()]
    blobs = fetch_svq_audio(flat)

    def svq_row(clip_id, r, category, tags, notes=""):
        dest = AUDIO / f"{clip_id}.wav"
        if not dest.exists():
            write_wav(dest, load_mono(io.BytesIO(blobs[r.utt_id])), TARGET_SR)
        return row(clip_id=clip_id, category=category, tags=tags, source_id=clip_id, speaker_id=r.speaker_id,
                   language=LANG[r.locale], input_path=f"data/audio/{clip_id}.wav", source_dataset="google/svq 1.0.0",
                   source_ref=f"{r.file}#{r.utt_id}", source_or_prompt=r.text, reference_transcript=r.text,
                   reference_origin="dataset prompt text (verify by listening)", license_or_consent=SVQ_LICENSE,
                   notes=f"{r.environment}; {r.speaker_gender}, age {r.speaker_age}. {notes}".strip())

    for prefix, category, tags in (("CL-EN", "clean_en", "clean;en;speaker"), ("CL-HI", "clean_hi", "clean;hi;speaker"),
                                   ("CL-TE", "clean_te", "clean;te;speaker"), ("NUM-EN", "numbers", "numbers;en"),
                                   ("NUM-HI", "numbers", "numbers;hi")):
        for i, r in enumerate(sel[prefix], 1):
            rows.append(svq_row(f"{prefix}-{i:02d}", r, category, tags))
    for key, cid, tags in (("RN-EN-BG", "RN-EN-01", "real_noise;background_speech;en"),
                           ("RN-EN-MEDIA", "RN-EN-02", "real_noise;media_noise;en"),
                           ("RN-HI-TRAFFIC", "RN-HI-01", "real_noise;traffic_noise;hi"),
                           ("RN-HI-BG", "RN-HI-02", "real_noise;background_speech;hi")):
        rows.append(svq_row(cid, sel[key][0], "real_noise", tags, "Recorded in a noisy room; not matched to a clean take."))
    for i, grp in enumerate(sel["RNP-TE"], 1):
        clean = grp[grp.environment == "clean"].sort_values("utt_id").iloc[0]
        noisy = grp[grp.environment == "traffic_noise"].sort_values("utt_id").iloc[0]
        rows.append(svq_row(f"RNP-TE-{i:02d}C", clean, "real_noise_pair", "real_noise_pair;clean;te"))
        r = svq_row(f"RNP-TE-{i:02d}N", noisy, "real_noise_pair", "real_noise_pair;traffic_noise;te",
                    f"Same speaker and text as RNP-TE-{i:02d}C (separate take). All RNP-TE pairs share one speaker.")
        r["source_id"] = f"RNP-TE-{i:02d}C"
        rows.append(r)

    print("2/6 FLEURS long sentences")
    rng = random.Random(SEED)
    for loc, lang, prefix in (("hi_in", "hi-IN", "LONG-HI"), ("te_in", "te-IN", "LONG-TE")):
        for i, p in enumerate(fleurs_long(loc, 2, rng), 1):
            cid = f"{prefix}-{i:02d}"
            dest = AUDIO / f"{cid}.wav"
            if not dest.exists():
                write_wav(dest, load_mono(CACHE / "fleurs" / p["file"]), TARGET_SR)
            rows.append(row(clip_id=cid, category="long", tags=f"long;{lang[:2]}", source_id=cid, language=lang,
                            input_path=f"data/audio/{cid}.wav", source_dataset=f"google/fleurs {loc} dev",
                            source_ref=f"{p['file']}#id{p['id']}", source_or_prompt=p["text"],
                            reference_transcript=p["text"], reference_origin="dataset raw transcription (verify by listening)",
                            license_or_consent=FLEURS_LICENSE, notes=f"Read sentence, {p['gender']}."))

    print("3/6 MUSAN noise")
    (mix_id, mix_noise), (ns_id, ns_noise) = musan_noises()

    print("4/6 derived clips")
    by_id = {r["clip_id"]: r for r in rows}
    for src_id in ("CL-EN-01", "CL-HI-01"):
        speech = load_mono(PROJECT / by_id[src_id]["input_path"])
        for snr in (20, 10, 0):
            cid = f"SNR-{src_id[3:5]}-{snr:02d}"
            mix, meta = mix_at_snr(speech, mix_noise, snr)
            write_wav(AUDIO / f"{cid}.wav", mix, TARGET_SR)
            src = by_id[src_id]
            rows.append(row(clip_id=cid, category="synthetic_noise", tags=f"synthetic_noise;snr{snr}",
                            source_id=src_id, speaker_id=src["speaker_id"], language=src["language"], noise_snr_db=snr,
                            input_path=f"data/audio/{cid}.wav", source_dataset=src["source_dataset"],
                            source_ref=src["source_ref"], source_or_prompt=src["source_or_prompt"],
                            reference_transcript=src["reference_transcript"], reference_origin=f"inherited from {src_id}",
                            license_or_consent=f"{src['license_or_consent']} + {MUSAN_LICENSE}",
                            derivation_json=json.dumps({"noise": mix_id, **meta}),
                            notes=f"{src_id} + MUSAN {mix_id} at {snr} dB active-speech SNR."))
    for src_id in ("CL-EN-02", "CL-HI-02"):
        src = by_id[src_id]
        outs = telephone_chain(PROJECT / src["input_path"], f"TEL-{src_id[3:5]}")
        for tag, path in outs.items():
            cid = path.stem
            codec = {"8K": "pcm_s16le 8 kHz", "ALAW": "G.711 A-law round trip", "ULAW": "G.711 mu-law round trip"}[tag]
            note = (f"Pre-codec control for TEL-{src_id[3:5]}-ALAW/ULAW." if tag == "8K"
                    else f"Encoded from exactly TEL-{src_id[3:5]}-8K.wav, decoded to 16-bit PCM for upload.")
            rows.append(row(clip_id=cid, category="telephony_sim", tags=f"telephony_sim;{tag.lower()}",
                            source_id=src_id if tag == "8K" else f"TEL-{src_id[3:5]}-8K", speaker_id=src["speaker_id"],
                            language=src["language"], codec=codec, input_path=f"data/audio/{cid}.wav",
                            source_dataset=src["source_dataset"], source_ref=src["source_ref"],
                            source_or_prompt=src["source_or_prompt"], reference_transcript=src["reference_transcript"],
                            reference_origin=f"inherited from {src_id}", license_or_consent=src["license_or_consent"],
                            derivation_json=json.dumps({"filter": "highpass 300 Hz, lowpass 3400 Hz, ffmpeg resample to 8 kHz",
                                                        "codec": codec}), notes=note))
    src = by_id["CL-EN-03"]
    paused, meta = insert_pause(load_mono(PROJECT / src["input_path"]))
    write_wav(AUDIO / "PAUSE-EN-01.wav", paused, TARGET_SR)
    rows.append(row(clip_id="PAUSE-EN-01", category="pause", tags="pause;en", source_id="CL-EN-03",
                    speaker_id=src["speaker_id"], language="en-IN", input_path="data/audio/PAUSE-EN-01.wav",
                    source_dataset=src["source_dataset"], source_ref=src["source_ref"],
                    source_or_prompt=src["source_or_prompt"], reference_transcript=src["reference_transcript"],
                    reference_origin="inherited from CL-EN-03", license_or_consent=src["license_or_consent"],
                    derivation_json=json.dumps(meta), notes="Mid-utterance pause + trailing silence; check for truncation."))
    write_wav(AUDIO / "NS-01.wav", np.zeros(4 * TARGET_SR), TARGET_SR)
    rows.append(row(clip_id="NS-01", category="no_speech", tags="no_speech;silence", source_id="NS-01",
                    input_path="data/audio/NS-01.wav", source_dataset="generated", source_or_prompt="4 s digital silence",
                    reference_transcript="", reference_origin="empty by construction", human_reference_verified="true",
                    is_no_speech="true", license_or_consent="generated", derivation_json=json.dumps({"seconds": 4})))
    seg = ns_noise[2 * TARGET_SR: 6 * TARGET_SR]
    seg = seg * (10 ** (-26 / 20) / np.sqrt(np.mean(seg ** 2)))
    write_wav(AUDIO / "NS-02.wav", np.clip(seg, -0.98, 0.98), TARGET_SR)
    rows.append(row(clip_id="NS-02", category="no_speech", tags="no_speech;ambient_noise", source_id="NS-02",
                    input_path="data/audio/NS-02.wav", source_dataset="MUSAN noise/free-sound",
                    source_ref=ns_id, source_or_prompt="4 s ambient background noise",
                    reference_transcript="", reference_origin="empty; listen to confirm no intelligible speech",
                    is_no_speech="true", license_or_consent=MUSAN_LICENSE,
                    derivation_json=json.dumps({"offset_s": 2.0, "seconds": 4, "rms_dbfs": -26})))

    print("5/6 test-call clips")
    for i, src_path in enumerate(select_calls(args.calls_root, args.n_calls), 1):
        cid = f"CALL-{i:02d}"
        dest = AUDIO / f"{cid}.wav"
        if not dest.exists():
            shutil.copyfile(src_path, dest)
        rel = src_path.relative_to(args.calls_root).as_posix()
        rows.append(row(clip_id=cid, category="real_telephony", tags="real_telephony", source_id=cid,
                        input_path=f"data/audio/{cid}.wav", source_dataset="internal test calls (Exotel, 8 kHz origin)",
                        source_ref=rel, reference_origin="to be transcribed by listener",
                        license_or_consent=CALL_LICENSE, notes="Language/code-switching to be tagged while listening."))

    print("6/6 manifest + listening sheet")
    manifest = PROJECT / "data" / "asr_manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} manifest rows -> {manifest.relative_to(PROJECT)}")
    subprocess.run([sys.executable, str(PROJECT / "scripts" / "make_listening_page.py")], check=True)


if __name__ == "__main__":
    main()
