from __future__ import annotations

# Builds an ASS subtitle file with word-level karaoke highlighting (TikTok/Reels
# style) plus an optional scene title at the top. Timings come straight from the
# Edge TTS WordBoundary events, so captions stay in sync with the voiceover.

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{fs},&H0000FFFF,&H00FFFFFF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,{outline},3,2,130,130,{cmv},1
Style: Title,{font},{tfs},&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,-1,0,0,0,100,100,0,0,1,{toutline},0,8,110,110,{tmv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _san(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(
    words: list[dict],
    width: int,
    height: int,
    path: str,
    scene_title: str = "",
    duration: float = 0.0,
    chunk_size: int = 3,
) -> None:
    fs = int(height * 0.048)
    tfs = int(height * 0.036)
    header = _HEADER.format(
        w=width, h=height, font="DejaVu Sans",
        fs=fs, outline=max(2, int(fs * 0.1)), cmv=int(height * 0.26),
        tfs=tfs, toutline=max(2, int(tfs * 0.1)), tmv=int(height * 0.07),
    )
    lines = [header]

    if scene_title and duration > 0:
        lines.append(
            f"Dialogue: 0,{_ts(0)},{_ts(duration)},Title,,0,0,0,,{{\\an8}}{_san(scene_title)}"
        )

    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    for chunk in chunks:
        if not chunk:
            continue
        start, end = chunk[0]["start"], chunk[-1]["end"]
        parts = []
        for w in chunk:
            dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
            parts.append(f"{{\\kf{dur_cs}}}{_san(w['text'])} ")
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Caption,,0,0,0,,{''.join(parts).strip()}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
