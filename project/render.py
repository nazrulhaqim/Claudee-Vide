"""Render the TikTok video: B-roll with motion + animated text + karaoke captions."""
import json, subprocess, sys, os, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from edit import *

SRC, WORK, OUT, MODE = sys.argv[1], sys.argv[2], sys.argv[3], (sys.argv[4] if len(sys.argv) > 4 else "final")
TL = json.load(open(f"{WORK}/timeline.json"))
TOTAL = TL["total"]; T = {s["id"]: s for s in TL["timeline"]}
NF = int(round(TOTAL * FPS))
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
MAXW = 960
OV = 1.15; BW, BH = int(W * OV) // 2 * 2, int(H * OV) // 2 * 2

def word_t(seg, sub, nth=0):
    hits = [a for a, b, w in T[seg]["words"] if sub.lower() in w.lower()]
    return hits[nth] if len(hits) > nth else T[seg]["start"]

# ---------- text rendering ----------
_fc = {}
def font(sz):
    if sz not in _fc: _fc[sz] = ImageFont.truetype(FONT, sz)
    return _fc[sz]
_ef = ImageFont.truetype(EMOJI, 109)
def is_emoji(ch): return ord(ch) >= 0x2190 and ch not in "→✔"
def emoji_img(ch, sz):
    im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), ch, font=_ef, embedded_color=True)
    im = im.crop(im.getbbox()); r = sz / 109 * 0.95
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)

def text_img(txt, sz, fill="#FFFFFF", stroke="#000000", sw=None, box=None, pad=(34, 18), radius=26,
             angle=0, shadow=True, colors=None):
    """Single-line rich text (emoji aware). colors: optional per-word fill list."""
    txt = txt.replace("️", "")
    sw = int(sz * 0.11) if sw is None else sw
    f = font(sz); asc, desc = f.getmetrics()
    runs, x = [], 0
    words = txt.split(" ")
    for wi, w in enumerate(words):
        col = colors[wi] if colors else fill
        for ch in w + (" " if wi < len(words) - 1 else ""):
            if is_emoji(ch):
                e = emoji_img(ch, sz); runs.append(("e", ch, x, e)); x += e.width + int(sz * 0.08)
            else:
                runs.append(("t", ch, x, col)); x += f.getlength(ch) * (1.7 if ch == " " else 1) + (sw * 0.25 if ch != " " else 0)
    tw, th = int(x) + 2 * sw, asc + desc + 2 * sw
    px, py = (pad if box else (0, 0))
    Wd, Hd = tw + 2 * px + 16, th + 2 * py + 16
    im = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if box:
        if shadow: d.rounded_rectangle((14, 16, Wd - 2, Hd - 0), radius, fill=(0, 0, 0, 140))
        d.rounded_rectangle((8, 8, Wd - 8, Hd - 8), radius, fill=box)
    ox, oy = 8 + px + sw, 8 + py + sw
    for kind, ch, rx, extra in runs:
        if kind == "t":
            if shadow and not box:
                d.text((ox + rx + 5, oy + 7), ch, font=f, fill=(0, 0, 0, 150), stroke_width=sw, stroke_fill=(0, 0, 0, 150))
            d.text((ox + rx, oy), ch, font=f, fill=extra, stroke_width=sw if stroke else 0, stroke_fill=stroke)
    for kind, ch, rx, e in runs:
        if kind == "e": im.alpha_composite(e, (int(ox + rx), int(oy + (asc - e.height) * 0.75)))
    if angle: im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if im.width > MAXW: im = im.resize((MAXW, int(im.height * MAXW / im.width)), Image.LANCZOS)
    return np.array(im)

def stack(imgs, gap=10):
    w = max(i.shape[1] for i in imgs); h = sum(i.shape[0] for i in imgs) + gap * (len(imgs) - 1)
    out = np.zeros((h, w, 4), np.uint8); y = 0
    for i in imgs:
        x = (w - i.shape[1]) // 2; out[y:y + i.shape[0], x:x + i.shape[1]] = i; y += i.shape[0] + gap
    return out

# ---------- overlay elements ----------
class El:
    def __init__(s, img, t0, t1, cx, cy, anim="pop", wiggle=0.0, pulse=0.0, shake=False):
        s.img, s.t0, s.t1, s.cx, s.cy, s.anim, s.wiggle, s.pulse, s.shake = img, t0, t1, cx, cy, anim, wiggle, pulse, shake
def ease_back(p):
    c1 = 2.2; c3 = c1 + 1; return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2

ELS = []
Y1 = "#FFE600"; ORANGE = "#FF6A00"; PINK = "#FF2E88"; CYAN = "#00C2FF"; GREEN = "#00C853"; RED = "#FF1744"
# Intro title
i0 = T["intro"]; iend = T["t1a"]["start"] - 0.25
ELS += [El(text_img("TIPS & TRICK", 112, Y1, angle=3), 0.05, iend, 540, 560),
        El(text_img("CUT COST", 196, "#FFFFFF", box=RED, angle=-4, pad=(40, 10)), 0.35, iend, 540, 760, shake=True),
        El(text_img("KABINET DAPUR 💸", 104, CYAN), 0.65, iend, 540, 960, wiggle=1.5)]
# Tip headers
tips = [("t1a", "t1c", "TIP #1", "PILIH MATERIAL BIJAK", ORANGE),
        ("t2a", "t2c", "TIP #2", "PENDEKKAN KABINET ATAS", PINK),
        ("t3a", "t3c", "TIP #3", "PILIH PAIP YANG BETUL", CYAN)]
for a, b, badge, head, col in tips:
    t0, t1 = T[a]["start"], T[b]["end"] + 0.1
    ELS += [El(text_img(badge, 84, "#000000", stroke=None, box=Y1, radius=40, pad=(40, 12)), t0, t1, 540, 300, anim="slide"),
            El(text_img(head, 76, "#FFFFFF", box=col, pad=(30, 14)), t0 + 0.15, t1, 540, 440, anim="slide_r")]
# Keyword pops
ELS += [El(stack([text_img("BLOCK BOARD", 104, "#FFFFFF", box=GREEN), text_img("atau", 60, Y1),
                  text_img("PLY BOARD", 104, "#FFFFFF", box=GREEN)], 6), word_t("t1b", "block"), T["t1b"]["end"] + 0.1, 540, 900, wiggle=1.2)]
for k, (lbl, w) in enumerate([("✅ HARGA BERPATUT", "harga"), ("✅ TAHAN AIR", "air"), ("✅ TAHAN ANAI-ANAI", "anai")]):
    ELS.append(El(text_img(lbl, 74, "#FFFFFF", box=(0, 0, 0, 185), pad=(28, 14)), word_t("t1c", w) - 0.05, T["t1c"]["end"] + 0.1, 540, 780 + k * 150, anim="slide"))
ELS += [El(stack([text_img("MAKIN TINGGI", 92, "#FFFFFF", box=RED), text_img("= MAKIN MAHAL ❗", 92, Y1)], 4),
           word_t("t2b", "tinggi") - 0.1, T["t2b"]["end"] + 0.1, 540, 900, shake=True),
        El(stack([text_img("5 KAKI → 3 KAKI", 112, Y1, box=(0, 0, 0, 200)), text_img("💰 JIMAT BAJET!", 92, "#FFFFFF", box=GREEN, angle=-3)], 14),
           word_t("t2c", "cut") - 0.05, T["t2c"]["end"] + 0.1, 540, 900, pulse=0.03),
        El(text_img("🤫 RAMAI TAK TAHU!", 96, "#000000", stroke=None, box=Y1, angle=-3), word_t("t3a", "ramai") - 0.1, T["t3a"]["end"] + 0.1, 540, 900, wiggle=2),
        El(text_img("BELI PAIP WALL MOUNT 🚰", 80, "#FFFFFF", box=CYAN), word_t("t3b", "beli"), T["t3b"]["end"] + 0.1, 540, 820, anim="slide"),
        El(text_img("IKUT PIPING RUMAH ✅", 80, "#000000", stroke=None, box="#FFFFFF"), word_t("t3b", "rumah"), T["t3b"]["end"] + 0.1, 540, 980, anim="slide_r"),
        El(stack([text_img("TAK PAYAH", 120, "#FFFFFF", box=GREEN, angle=-5), text_img("KOS LEBIH! 💸", 120, Y1, angle=-5)], 0),
           T["t3c"]["start"], T["out"]["start"] - 0.15, 540, 900, shake=True),
        # Outro
        El(text_img("NAK HARGA KABINET?", 84, "#FFFFFF", box=PINK), T["out"]["start"], TOTAL, 540, 380, anim="slide"),
        El(text_img("SLIDE DM SEKARANG 📩", 96, "#000000", stroke=None, box=Y1, pad=(40, 22)), word_t("out", "slide") - 0.2, TOTAL, 540, 860, pulse=0.05),
        El(text_img("SAVE • LIKE • SHARE ❤️", 72, "#FFFFFF", box=(0, 0, 0, 190)), T["out"]["end"] + 0.05, TOTAL, 540, 1060, anim="slide_r")]

# ---------- captions (karaoke) ----------
CAPS = []
for seg in TL["timeline"]:
    ws = [w for w in seg["words"] if w[2]]
    chunk = []
    for i, w in enumerate(ws):
        chunk.append(w)
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        if len(chunk) >= 3 or nxt is None or w[2][-1] in ",." or (nxt and nxt[0] - w[1] > 0.35):
            CAPS.append(list(chunk)); chunk = []
cap_cache = {}
def caption_img(ci, wi):
    key = (ci, wi)
    if key not in cap_cache:
        words = [w[2].upper().strip(",.") for w in CAPS[ci]]
        cols = ["#FFFFFF"] * len(words); cols[wi] = Y1
        cap_cache[key] = text_img(" ".join(words), 78, colors=cols, sw=10)
    return cap_cache[key]
CAP_T = []
for ci, ch in enumerate(CAPS):
    end = CAPS[ci + 1][0][0] if ci + 1 < len(CAPS) and CAPS[ci + 1][0][0] - ch[-1][1] < 0.5 else ch[-1][1] + 0.25
    CAP_T.append((ch[0][0], end))

# ---------- shots ----------
shots = []
for i, (sid, off, src, ss) in enumerate(SHOTS):
    t0 = 0.0 if i == 0 else T[sid]["start"] + off
    if sid in TIP_STARTS and off == 0: t0 -= 0.25   # cut on the whoosh, before the voice
    shots.append([t0, src, ss, sid in TIP_STARTS and off == 0])
for i, s in enumerate(shots): s.append(shots[i + 1][0] if i + 1 < len(shots) else TOTAL)

def reader(src, ss, dur):
    vf = (f"scale={BW}:{BH}:force_original_aspect_ratio=increase,crop={BW}:{BH},fps={FPS},"
          "eq=contrast=1.07:saturation=1.28:brightness=0.015:gamma=1.02,unsharp=5:5:0.6")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(ss), "-i", f"{SRC}/{src}.mp4", "-t", str(dur + 0.5),
                          "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    last = None
    while True:
        b = p.stdout.read(BW * BH * 3)
        if len(b) == BW * BH * 3: last = np.frombuffer(b, np.uint8).reshape(BH, BW, 3)
        yield last

# vignette/gradient for text readability
yy = np.linspace(0, 1, H)[:, None]
SHADE = (1 - 0.45 * np.clip(1 - yy / 0.28, 0, 1) ** 1.5 - 0.35 * np.clip((yy - 0.62) / 0.38, 0, 1) ** 1.5).astype(np.float32)[..., None]

def blend(frame, rgba, cx, cy, sc=1.0, alpha=1.0, ang=0.0):
    if alpha <= 0.01 or sc <= 0.02: return
    h, w = rgba.shape[:2]
    if abs(sc - 1) > 1e-3 or abs(ang) > 1e-3:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, sc)
        nw, nh = int(w * sc * 1.2) + 4, int(h * sc * 1.2) + 4
        M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
        rgba = cv2.warpAffine(rgba, M, (nw, nh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        h, w = nh, nw
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if fx0 >= fx1 or fy0 >= fy1: return
    sub = rgba[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0].astype(np.float32)
    a = sub[..., 3:4] / 255 * alpha
    reg = frame[fy0:fy1, fx0:fx1]
    reg[:] = reg * (1 - a) + sub[..., :3] * a

def draw_el(frame, e, t):
    if not (e.t0 <= t < e.t1): return
    lt, rem = t - e.t0, e.t1 - t
    sc, al, dx, ang, dy = 1.0, 1.0, 0, 0.0, 0
    if e.anim == "pop":
        p = min(1, lt / 0.28); sc = max(0.0, ease_back(p)) if p < 1 else 1.0; al = min(1, lt / 0.08)
    else:
        p = min(1, lt / 0.3); k = 1 - (1 - p) ** 3; dx = (-1 if e.anim == "slide" else 1) * (1 - k) * 1100
    if e.wiggle: ang = e.wiggle * math.sin(lt * 5)
    if e.pulse: sc *= 1 + e.pulse * math.sin(lt * 9)
    if e.shake and lt < 0.35: dx += 14 * math.sin(lt * 90) * (1 - lt / 0.35); dy += 8 * math.cos(lt * 70) * (1 - lt / 0.35)
    if rem < 0.15: al *= rem / 0.15; sc *= 0.9 + 0.1 * rem / 0.15
    blend(frame, e.img, e.cx + dx, e.cy + dy, sc, al, ang)

enc_vf = "scale=540:960:flags=lanczos,drawtext=fontfile=" + FONT + ":text='PREVIEW':x=w-tw-14:y=14:fontsize=26:fontcolor=white@0.6" if MODE == "preview" else "null"
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-i", f"{WORK}/mix.wav", "-vf", enc_vf, "-c:v", "libx264", "-preset", "medium" if MODE == "preview" else "slow",
                        "-crf", "26" if MODE == "preview" else "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
si, rd = -1, None
for fi in range(NF):
    t = fi / FPS
    while si + 1 < len(shots) and t >= shots[si + 1][0]:
        si += 1; s = shots[si]; rd = reader(s[1], s[2], s[4] - s[0])
    s = shots[si]; src = next(rd); lt = t - s[0]; dur = s[4] - s[0]
    # motion: punch-in at cut + slow push / drift
    z = 1.0 + 0.07 * (lt / dur) + 0.16 * max(0, 1 - lt / 0.3) ** 3
    if fi < 6: z += 0.04 * (6 - fi)
    cw, chh = BW / z, BH / z
    drift = (si % 2 * 2 - 1) * 0.5 * (BW - cw) * (lt / dur - 0.5)
    x0 = (BW - cw) / 2 + drift; y0 = (BH - chh) / 2
    frame = cv2.resize(src[int(y0):int(y0 + chh), int(x0):int(x0 + cw)], (W, H), interpolation=cv2.INTER_AREA)
    # whip blur around tip transitions
    nxt = shots[si + 1] if si + 1 < len(shots) else None
    blur = 0
    if s[3] and lt < 0.15: blur = int(70 * (1 - lt / 0.15))
    if nxt and nxt[3] and s[4] - t < 0.12: blur = int(70 * (1 - (s[4] - t) / 0.12))
    if blur > 2:
        k = np.zeros((1, blur), np.float32); k[0, :] = 1 / blur; frame = cv2.filter2D(frame, -1, k)
    frame = frame.astype(np.float32) * SHADE
    if s[3] and lt < 0.12: frame += (255 - frame) * (0.55 * (1 - lt / 0.12))
    for e in ELS: draw_el(frame, e, t)
    for ci, (c0, c1) in enumerate(CAP_T):
        if c0 <= t < c1:
            wi = max([i for i, w in enumerate(CAPS[ci]) if w[0] <= t + 0.03] or [0])
            p = min(1, (t - c0) / 0.12)
            blend(frame, caption_img(ci, wi), 540, 1330, 0.85 + 0.15 * p, 1.0)
    enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    if fi % 150 == 0: print(f"frame {fi}/{NF}", flush=True)
enc.stdin.close(); enc.wait(); print("done", OUT)
