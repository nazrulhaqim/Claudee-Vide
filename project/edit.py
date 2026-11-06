"""Edit decision list for 'Tips & Trick Cut Cost Kabinet Dapur' (TikTok 9:16)."""
FPS = 30
W, H = 1080, 1920
TEMPO = 1.08          # gentle speed-up for punchier delivery (pitch preserved)
GAP_IN, GAP_TIP = 0.12, 0.40

# Voice cuts: id, file, start, end (seconds in original recording)
VOICE = [
    ("intro", "a0_intro", 0.00, 5.10),
    ("t1a",   "a1_tips1", 0.00, 3.30),
    ("t1b",   "a1_tips1", 31.50, 34.20),
    ("t1c",   "a1_tips1", 36.28, 40.45),
    ("t2a",   "a2_tips2", 0.00, 2.20),
    ("t2b",   "a2_tips2", 5.95, 8.95),
    ("t2c",   "a2_tips2", 9.20, 13.42),
    ("t3a",   "a3_tips3", 0.00, 3.10),
    ("t3b",   "a3_tips3", 52.25, 59.55),
    ("t3c",   "a3_tips3", 60.10, 61.30),
    ("out",   "a4_outro", 4.50, 6.62),
]
TIP_STARTS = {"t1a", "t2a", "t3a", "out"}
END_HOLD = 1.5   # end card after last word

# Word fixes for captions (whisper -> correct Malay / terms)
FIX = {"jemah": "jimat", "sepertama": "pertama", "play": "ply", "dengar": "tahan",
       "Dead": "deck", "Mountain": "mount", "Mountain.": "mount", "Mountain,": "mount,",
       "pipe": "paip", "pipe,": "paip,", "kurang": "korang", "Wall": "wall",
       "Tip": "Tips", "anak": "anai", "-anak": "-anai", "Fawcet": "faucet"}

# B-roll shots: (voice id the shot starts on, offset into that segment, source, src start)
SHOTS = [
    ("intro", 0.0, "v_0818_122427", 0.5),
    ("intro", 2.4, "v_WA1019", 8.0),
    ("t1a",   0.0, "v_0910_135427", 0.0),
    ("t1b",   0.0, "v_0910_135427", 4.3),
    ("t1c",   0.0, "v_WA0912", 17.5),
    ("t2a",   0.0, "v_WA0411", 0.3),
    ("t2b",   0.0, "v_WA1019", 0.0),
    ("t2c",   0.0, "v_1026_190404", 0.0),
    ("t3a",   0.0, "v_0727_141413", 6.6),
    ("t3b",   0.0, "v_0727_141413", 9.6),
    ("t3b",   3.0, "v_WA1019", 10.6),
    ("t3c",   0.0, "v_WA0430", 0.0),
    ("out",   0.0, "v_WA0430", 4.0),
]
