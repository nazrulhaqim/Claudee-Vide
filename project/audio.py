"""Build the audio: studio-enhanced voice cuts + synthesized music bed + SFX."""
import json, subprocess, sys, os, wave
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from edit import *

SRC, WORK = sys.argv[1], sys.argv[2]
SR = 48000
os.makedirs(WORK, exist_ok=True)

VOICE_FX = ("highpass=f=80,lowpass=f=14500,"
            "afftdn=nr=14:nf=-32:tn=1,"
            "equalizer=f=220:t=q:w=1.0:g=-3,"      # remove boxiness/mud
            "equalizer=f=120:t=q:w=0.8:g=2,"       # warmth / radio body
            "equalizer=f=3200:t=q:w=1.2:g=3.5,"    # presence
            "equalizer=f=9500:t=q:w=1.0:g=2.5,"    # air
            "deesser=i=0.45,"
            "acompressor=threshold=-22dB:ratio=3.5:attack=4:release=90:makeup=5,"
            "alimiter=limit=0.89")

def run(cmd): subprocess.run(cmd, check=True)
def load(p):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, w.getnchannels()).mean(1)
def save(p, a):
    a = np.clip(a, -1, 1); st = a if a.ndim == 2 else np.stack([a, a], 1)
    w = wave.open(p, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()

# 1) enhance each recording
enh = {}
for f in sorted({v[1] for v in VOICE}):
    out = f"{WORK}/enh_{f}.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", f"{SRC}/{f}.m4a", "-af", VOICE_FX, "-ar", str(SR), "-ac", "1", out])
    enh[f] = load(out)

# 2) cut + concat
words = json.load(open(f"{WORK}/transcript.json"))
pieces, timeline, t = [], [], 0.0
for i, (vid, f, s, e) in enumerate(VOICE):
    if i:
        gap = GAP_TIP if vid in TIP_STARTS else GAP_IN
        pieces.append(np.zeros(int(gap * SR), np.float32)); t += gap
    seg = enh[f][int(s * SR):int(e * SR)].copy()
    fl = int(0.02 * SR); seg[:fl] *= np.linspace(0, 1, fl); seg[-fl:] *= np.linspace(1, 0, fl)
    ws = []
    for sg in words[f"{f}.wav"]:
        for ws0, we0, wt in sg["w"]:
            mid = (ws0 + we0) / 2
            if s <= mid <= e:
                txt = wt.strip(); txt = FIX.get(txt, txt)
                ws.append([(t + max(ws0, s) - s) / TEMPO, (t + min(we0, e) - s) / TEMPO, txt])
    merged = []
    for w in ws:
        if w[2].startswith("-") and merged: merged[-1][2] += w[2]; merged[-1][1] = w[1]
        elif w[2].lower().startswith("air") and merged and "anai" in merged[-1][2]: merged[-1][1] = w[1]; merged[-1][2] += "."
        else: merged.append(w)
    ws = merged
    timeline.append({"id": vid, "start": t / TEMPO, "end": (t + len(seg) / SR) / TEMPO, "words": ws})
    pieces.append(seg); t += len(seg) / SR
voice = np.concatenate(pieces)
save(f"{WORK}/voice_raw.wav", voice)
run(["ffmpeg", "-v", "error", "-y", "-i", f"{WORK}/voice_raw.wav", "-af",
     f"atempo={TEMPO},loudnorm=I=-15:TP=-1.5:LRA=7", "-ar", str(SR), f"{WORK}/voice.wav"])
voice = load(f"{WORK}/voice.wav")
total = timeline[-1]["end"] + END_HOLD
N = int(total * SR)
voice = np.pad(voice, (0, max(0, N - len(voice))))[:N]

# 3) music bed (synth, 112 BPM, I-V-vi-IV)
rng = np.random.default_rng(7)
tt = np.arange(N) / SR
bpm = 112; beat = 60 / bpm
music = np.zeros(N, np.float32)
def add(buf, at, snd, g=1.0):
    i = int(at * SR)
    if i >= len(buf): return
    n = min(len(snd), len(buf) - i); buf[i:i + n] += g * snd[:n]
def env(n, a=0.005, d=0.2):
    x = np.arange(n) / SR; return np.minimum(x / a, 1) * np.exp(-x / d)
def kick():
    n = int(0.35 * SR); x = np.arange(n) / SR
    f = 50 + 110 * np.exp(-x * 30); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9)
def hat():
    n = int(0.05 * SR); s = rng.standard_normal(n); s = np.diff(s, prepend=0); return s * env(n, 0.001, 0.015) * 0.3
def clap():
    n = int(0.2 * SR); s = rng.standard_normal(n); s = s - np.convolve(s, np.ones(8) / 8, "same"); return s * env(n, 0.002, 0.06) * 0.6
chords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
def note(m, dur, kind="pad"):
    n = int(dur * SR); x = np.arange(n) / SR; fr = 440 * 2 ** ((m - 69) / 12)
    if kind == "bass":
        s = np.sign(np.sin(2 * np.pi * fr * x)) * 0.3 + np.sin(2 * np.pi * fr * x)
        s = np.convolve(s, np.ones(30) / 30, "same"); return s * env(n, 0.005, 0.25) * 0.5
    s = sum(np.sin(2 * np.pi * fr * k * x + k) / k for k in (1, 2, 3)) * 0.25
    return s * np.minimum(x / 0.05, 1) * np.minimum((dur - x) / 0.2, 1).clip(0, 1)
nb = int(total / beat) + 1
for b in range(nb):
    at = b * beat
    add(music, at, kick(), 0.9)
    if b % 2 == 1: add(music, at, clap(), 0.8)
    add(music, at + beat / 2, hat(), 1.0); add(music, at, hat(), 0.6)
    if b % 4 == 0:
        ch = chords[(b // 4) % 4]
        for m in ch: add(music, at, note(m, beat * 4), 0.35)
    ch = chords[(b // 4) % 4]
    add(music, at, note(ch[0] - 24, beat * 0.9, "bass"), 0.9)
    add(music, at + beat / 2, note(ch[0] - 12, beat * 0.4, "bass"), 0.4)
music /= np.abs(music).max() + 1e-9
# sidechain duck under voice
venv = np.convolve(np.abs(voice), np.ones(int(0.05 * SR)) / int(0.05 * SR), "same")
venv = np.convolve((venv > 0.02).astype(np.float32), np.ones(int(0.25 * SR)) / int(0.25 * SR), "same").clip(0, 1)
music *= (0.16 - 0.10 * venv)
music[:int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))
music[-int(1.0 * SR):] *= np.linspace(1, 0, int(1.0 * SR))

# 4) SFX
def whoosh(d=0.45):
    n = int(d * SR); s = rng.standard_normal(n); x = np.arange(n) / n
    out = np.zeros(n); y = 0; 
    cut = 0.02 + 0.25 * np.sin(np.pi * x) ** 2
    for i in range(n): y += cut[i] * (s[i] - y); out[i] = y
    return out * np.sin(np.pi * x) ** 1.5 * 2.2
def pop():
    n = int(0.12 * SR); x = np.arange(n) / SR; f = 900 * np.exp(-x * 25) + 300
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 35) * 0.9
def ding(f0=1568):
    n = int(1.2 * SR); x = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f0 * r * x) * np.exp(-x * dk) * g for r, dk, g in ((1, 3, .5), (2.76, 6, .25), (5.4, 10, .12))) * 0.9
def cash():
    n = int(0.06 * SR); clk = rng.standard_normal(n) * env(n, 0.001, 0.01)
    s = np.zeros(int(1.2 * SR)); s[:n] += clk; s[int(0.05 * SR):int(0.05 * SR) + n] += clk
    d = ding(2637) * 0.7 + ding(3520) * 0.4; s[int(0.08 * SR):] += d[:len(s) - int(0.08 * SR)]; return s
def boom():
    n = int(1.0 * SR); x = np.arange(n) / SR; f = 35 + 60 * np.exp(-x * 6)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 3.5) + rng.standard_normal(n) * np.exp(-x * 20) * 0.15)
def riser(d=0.9):
    n = int(d * SR); x = np.arange(n) / n; s = rng.standard_normal(n)
    y = np.zeros(n); v = 0
    for i in range(n): v += (0.01 + 0.3 * x[i] ** 2) * (s[i] - v); y[i] = v
    return y * x ** 2 * 2
sfx = np.zeros(N, np.float32)
T = {seg["id"]: seg for seg in timeline}
def wt(word_sub, seg_id):  # time of first word containing substring
    for a, b, w in T[seg_id]["words"]:
        if word_sub.lower() in w.lower(): return a
    return T[seg_id]["start"]
events = [(0.0, boom(), 0.8), (0.05, pop(), 0.6), (0.35, pop(), 0.6), (0.65, pop(), 0.6)]
for sid in ("t1a", "t2a", "t3a", "out"):
    events += [(T[sid]["start"] - 0.32, whoosh(), 0.6), (T[sid]["start"] + 0.02, pop(), 0.5)]
events += [(T["t1b"]["start"], pop(), 0.5), (wt("tahan", "t1c"), ding(), 0.35), (wt("air", "t1c"), ding(1760), 0.35),
           (wt("anai", "t1c") , ding(1976), 0.35),
           (wt("mahal", "t2b"), pop(), 0.6), (wt("cut", "t2c"), cash(), 0.45),
           (T["t3a"]["start"] + 0.05, riser(0.8), 0.25),
           (wt("wall", "t3b"), pop(), 0.5), (T["t3c"]["start"], cash(), 0.5),
           (T["out"]["end"] + 0.1, ding(2093), 0.4)]
for at, snd, g in events: add(sfx, max(0, at), snd.astype(np.float32), g)

mix = voice + music + sfx * 0.55
save(f"{WORK}/mix_raw.wav", mix)
run(["ffmpeg", "-v", "error", "-y", "-i", f"{WORK}/mix_raw.wav", "-af", "loudnorm=I=-14:TP=-1:LRA=9", "-ar", str(SR), f"{WORK}/mix.wav"])
json.dump({"total": total, "timeline": timeline}, open(f"{WORK}/timeline.json", "w"), indent=1, ensure_ascii=False)
print("total", round(total, 2))
for seg in timeline: print(seg["id"], round(seg["start"], 2), round(seg["end"], 2), " ".join(w[2] for w in seg["words"]))
