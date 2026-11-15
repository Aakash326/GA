"""Report charts from saved results (no API calls). Writes PNGs to results/charts/.

Palette: reference categorical slots 1-3 (blue, orange, aqua), which validate all-pairs for colour-vision deficiency;
text in ink tokens, recessive grid, thin marks, direct labels on every bar (few bars), one axis per chart.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "results" / "charts"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e2e1dc", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=160)
    plt.close(fig)
    print("wrote", (OUT / name).relative_to(PROJECT))


def asr_by_language():
    d = pd.read_csv(PROJECT / "results/asr_results_labelled.csv", encoding="utf-8-sig")
    d["lang"] = d["language"].str.split(",").str[0]
    g = d.groupby("lang")
    t = pd.DataFrame({"n": g.size(), "ref_words": g["ref_word_count"].sum(),
                      "wer": g["word_edits"].sum() / g["ref_word_count"].sum(),
                      "cer": g["nospace_char_edits"].sum() / g["nospace_ref_chars"].sum()})
    names = {"en-IN": "English", "hi-IN": "Hindi", "te-IN": "Telugu", "ta-IN": "Tamil", "kn-IN": "Kannada", "mr-IN": "Marathi"}
    t = t.reindex(["en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "mr-IN"])
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    y = range(len(t))
    h = 0.36
    # Review fix 1: no "script-adjusted" WER (the heuristic removed real errors). Two honest measures only.
    for k, (col, color, label) in enumerate([("wer", BLUE, "WER (normalised)"), ("cer", AQUA, "CER (spaces ignored)")]):
        ys = [i + (k - 0.5) * (h + 0.03) for i in y]
        ax.barh(ys, t[col] * 100, height=h, color=color, label=label)
        for yy, v in zip(ys, t[col]):
            ax.text(v * 100 + 0.6, yy, f"{v*100:.1f}", va="center", fontsize=8, color=INK2)
    ax.set_yticks(list(y), [f"{names[l]}  (n={int(t.loc[l,'n'])})" for l in t.index], color=INK)
    ax.invert_yaxis()
    ax.set_xlabel("error rate (%)")
    ax.set_title("Prisma v3.0 error by language (scored speech clips)", loc="left", color=INK, fontsize=11)
    ax.set_xlim(0, t[["wer", "cer"]].max().max() * 100 * 1.12)
    ax.legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    ax.set_title("Prisma v3.0 error by language (scored speech clips)", loc="left", color=INK, fontsize=11, pad=24)
    ax.grid(axis="y", visible=False)
    save(fig, "asr_by_language.png")


def asr_paired():
    p = pd.read_csv(PROJECT / "results/asr_paired_deltas.csv", encoding="utf-8-sig")
    order = [("noise 20 dB SNR vs clean", "noise\n20 dB"), ("noise 10 dB SNR vs clean", "noise\n10 dB"),
             ("noise 0 dB SNR vs clean", "noise\n0 dB"), ("8 kHz band-limited vs clean (bandwidth)", "8 kHz\nphone band"),
             ("A-law vs 8 kHz PCM (codec only)", "G.711\nA-law"), ("μ-law vs 8 kHz PCM (codec only)", "G.711\nμ-law")]
    vals, ns = [], []
    for cond, _ in order:
        s = p[p["condition"] == cond]
        vals.append(100 * (s["word_edits"].sum() - s["src_word_edits"].sum()) / s["ref_words"].sum())
        ns.append(len(s))
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    xs = range(len(order))
    ax.bar(xs, vals, width=0.55, color=BLUE)
    for x, v, n in zip(xs, vals, ns):
        ax.text(x, v + 0.3, f"+{v:.1f} pp\n(n={n})", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.set_xticks(list(xs), [l for _, l in order], color=INK)
    ax.set_ylabel("WER change vs matched source (pp)")
    ax.set_ylim(0, max(vals) * 1.35 + 1)
    ax.set_title("Same audio, one change: noise hurts at 0 dB; no loss seen in the phone-channel pairs", loc="left", color=INK, fontsize=11)
    ax.grid(axis="x", visible=False)
    save(fig, "asr_noise_phone.png")


def tts_accuracy():
    path = PROJECT / "results/tts_scored_targets.csv"
    if not path.exists():
        print("skip tts_accuracy (run the notebook first)")
        return
    d = pd.read_csv(path, encoding="utf-8-sig")
    d = d[d["final_result"].isin(["correct", "wrong", "ambiguous"])]
    g = d.groupby("category")
    t = pd.DataFrame({"n": g.size(), "acc": g["final_result"].apply(lambda s: (s == "correct").mean()),
                      "human": g["source"].apply(lambda s: (s == "human").sum())}).sort_values("acc")
    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    ax.barh(range(len(t)), t["acc"] * 100, height=0.55, color=BLUE)
    for i, (cat, r) in enumerate(t.iterrows()):
        ax.text(r["acc"] * 100 + 0.8, i, f"{r['acc']*100:.0f}%  ({int(r['n'])} targets, {int(r['human'])} human-scored)",
                va="center", fontsize=8, color=INK2)
    ax.set_yticks(range(len(t)), [c.replace("_", " ") for c in t.index], color=INK)
    ax.set_xlim(0, 168)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("targets correct (%)")
    ax.set_title("Timbre v3.0: targets correct by category (listener marks, else calibrated judge)", loc="left", color=INK, fontsize=10.5)
    ax.grid(axis="y", visible=False)
    save(fig, "tts_accuracy_by_category.png")


def tts_latency():
    d = pd.read_csv(PROJECT / "results/tts_ws_vs_sse.csv", encoding="utf-8-sig")
    d = d[d["case_id"] == "T31"]
    groups = [("v2.5", "SSE", "new request"), ("v2.5", "WebSocket", "cold"), ("v2.5", "WebSocket", "warm"),
              ("v3.0", "SSE", "new request"), ("v3.0", "WebSocket", "cold"), ("v3.0", "WebSocket", "warm")]
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    for i, (m, tr, conn) in enumerate(groups):
        s = d[(d["model"] == m) & (d["transport"] == tr) & (d["connection"] == conn)]["smooth_total_ms"] / 1000   # end-to-end: WebSocket connect included (review fix 2)
        color = AQUA if m == "v2.5" else BLUE
        ax.scatter([i] * len(s), s, s=36, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=3,
                   label=("Timbre v2.5 (Kaveri)" if m == "v2.5" else "Timbre v3.0 (Tarika)") if conn in ("new request",) else None)
        med = s.median()
        ax.plot([i - 0.25, i + 0.25], [med, med], color=INK, linewidth=2, zorder=4)
        ax.text(i + 0.3, med, f"{med:.2f} s", va="center", fontsize=8, color=INK2)
    ax.set_xticks(range(len(groups)), [f"{m}\n{tr}\n{'keep-alive' if conn == 'new request' else conn}" for m, tr, conn in groups],
                  color=INK, fontsize=8)
    ax.set_ylabel("wait until smooth speech (s)")
    ax.set_title("Streaming: end-to-end wait to smooth speech (5 runs; cold includes connect)", loc="left", color=INK, fontsize=9.5)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.grid(axis="x", visible=False)
    save(fig, "tts_streaming_latency.png")


def tts_rest_latency():
    d = pd.read_csv(PROJECT / "results/tts_results.csv", encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.scatter(d["audio_duration_s"], d["response_latency_ms"] / 1000, s=22, color=BLUE, edgecolor=SURFACE, linewidth=1, zorder=3)
    ax.set_xlabel("audio produced (s)")
    ax.set_ylabel("time until whole file arrives (s)")
    ax.set_title("Whole-file REST (v3.0, 98 prompts): the caller waits for the entire reply", loc="left", color=INK, fontsize=10.5)
    ax.set_ylim(0, 13.5)
    for x, y, lab in [(53.28, 8.07, "T25 (930 chars)"), (74.72, 11.59, "T88 (1,281 chars)")]:
        ax.annotate(lab, (x, y), xytext=(-70, 6), textcoords="offset points", fontsize=8, color=INK2)
    save(fig, "tts_rest_latency.png")


if __name__ == "__main__":
    asr_by_language()
    asr_paired()
    tts_accuracy()
    tts_latency()
    tts_rest_latency()
