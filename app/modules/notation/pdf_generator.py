"""
Drum Notation PDF Generator
Draws a real 5-line percussion staff with standard B&W musical notation.
Instruments at conventional staff positions; oval heads for drums, X for cymbals.
"""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas

# ---------------------------------------------------------------------------
# Drum map: staff_pos = 0 (bottom line) .. 4 (top line), 0.5 = spaces
# head : "oval" | "x" | "x_open" | "diamond" | "x_slash"
# stem : "up" | "down"
# ---------------------------------------------------------------------------
DRUM_MAP: Dict[str, Dict] = {
    "china":        {"staff_pos": 5.5,  "head": "x_slash", "stem": "up",   "label": "China"},
    "crash2":       {"staff_pos": 5.0,  "head": "x",       "stem": "up",   "label": "Crash 2"},
    "crash":        {"staff_pos": 4.5,  "head": "x",       "stem": "up",   "label": "Crash"},
    "hihat_open":   {"staff_pos": 4.0,  "head": "x_open",  "stem": "up",   "label": "Open Hi-Hat"},
    "ride_bell":    {"staff_pos": 4.0,  "head": "diamond", "stem": "up",   "label": "Ride Bell"},
    "ride":         {"staff_pos": 3.5,  "head": "x",       "stem": "up",   "label": "Ride"},
    "hi-hat":       {"staff_pos": 3.5,  "head": "x",       "stem": "up",   "label": "Hi-Hat"},
    "hihat_closed": {"staff_pos": 3.5,  "head": "x",       "stem": "up",   "label": "Hi-Hat"},
    "tom1":         {"staff_pos": 3.0,  "head": "oval",    "stem": "up",   "label": "Tom 1"},
    "tom2":         {"staff_pos": 2.5,  "head": "oval",    "stem": "up",   "label": "Tom 2"},
    "snare":        {"staff_pos": 2.0,  "head": "oval",    "stem": "up",   "label": "Snare"},
    "floor_tom":    {"staff_pos": 1.0,  "head": "oval",    "stem": "down", "label": "Floor Tom"},
    "kick":         {"staff_pos": -0.5, "head": "oval",    "stem": "down", "label": "Kick"},
    "bass_drum":    {"staff_pos": -0.5, "head": "oval",    "stem": "down", "label": "Kick"},
    "foot_hihat":   {"staff_pos": -1.5, "head": "x",       "stem": "down", "label": "Foot Hi-Hat"},
}

DRUM_ALIASES: Dict[str, str] = {
    "hi_hat": "hi-hat", "hihat": "hi-hat", "hi hat": "hi-hat",
    "bass drum": "kick", "bd": "kick", "sd": "snare",
    "hh": "hi-hat", "hhc": "hihat_closed", "hho": "hihat_open",
    "cc": "crash", "rc": "ride", "t1": "tom1", "t2": "tom2",
    "ft": "floor_tom", "fhh": "foot_hihat",
}

STAFF_LINES = 5
LS = 7.0   # points between adjacent staff lines


def _norm(raw: str) -> str:
    k = raw.strip().lower()
    return DRUM_ALIASES.get(k, k)


def _info(raw: str) -> Dict:
    k = _norm(raw)
    return DRUM_MAP.get(k, {"staff_pos": 2.0, "head": "oval", "stem": "up", "label": k.title()})


def _sy(y_bot: float, sp: float) -> float:
    """Convert staff position to canvas y."""
    return y_bot + sp * LS


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_staff(c, x: float, y_bot: float, w: float):
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.7)
    for i in range(STAFF_LINES):
        yy = _sy(y_bot, i)
        c.line(x, yy, x + w, yy)


def _draw_perc_clef(c, x: float, y_bot: float) -> float:
    """Draw double-bar percussion clef. Returns x coordinate after the clef."""
    c.setFillColor(colors.black)
    h = (STAFF_LINES - 1) * LS
    bw, gap = 3.5, 4.5
    c.rect(x, y_bot, bw, h, fill=1, stroke=0)
    c.rect(x + bw + gap, y_bot, bw, h, fill=1, stroke=0)
    return x + bw * 2 + gap + 5.0


def _draw_time_sig(c, x: float, y_bot: float, ts: str) -> float:
    parts = ts.split("/") if "/" in ts else ["4", "4"]
    num = parts[0].strip()
    den = parts[1].strip() if len(parts) > 1 else "4"
    fs = LS * 1.9
    c.setFont("Helvetica-Bold", fs)
    c.setFillColor(colors.black)
    mid = y_bot + (STAFF_LINES - 1) * LS / 2
    c.drawCentredString(x + 6, mid + LS * 0.45, num)
    c.drawCentredString(x + 6, mid - LS * 1.15, den)
    return x + 16.0


def _draw_barline(c, x: float, y_bot: float, final: bool = False):
    y_top = y_bot + (STAFF_LINES - 1) * LS
    c.setStrokeColor(colors.black)
    if final:
        c.setLineWidth(0.7)
        c.line(x - 4, y_bot, x - 4, y_top)
        c.setLineWidth(3.0)
        c.line(x, y_bot, x, y_top)
    else:
        c.setLineWidth(0.7)
        c.line(x, y_bot, x, y_top)


def _draw_ledger(c, bx: float, y_bot: float, sp: float):
    """Short ledger lines for notes outside the 5-line staff."""
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.7)
    lw = 8.0
    if sp < 0:
        pos = -1.0
        while pos >= sp - 0.01:
            c.line(bx - lw, _sy(y_bot, pos), bx + lw, _sy(y_bot, pos))
            pos -= 1.0
    elif sp > 4:
        pos = 5.0
        while pos <= sp + 0.01:
            c.line(bx - lw, _sy(y_bot, pos), bx + lw, _sy(y_bot, pos))
            pos += 1.0


def _draw_head(c, x: float, y: float, head: str, sz: float = 4.0):
    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)
    hw, hh = sz * 1.4, sz * 0.95

    if head == "oval":
        c.saveState()
        c.translate(x, y)
        c.rotate(18)
        c.ellipse(-hw * 0.5, -hh * 0.5, hw * 0.5, hh * 0.5, fill=1, stroke=0)
        c.restoreState()

    elif head == "x":
        c.setLineWidth(1.3)
        d = sz * 0.8
        c.line(x - d, y - d, x + d, y + d)
        c.line(x - d, y + d, x + d, y - d)

    elif head == "x_open":
        c.setLineWidth(1.0)
        r = sz * 0.85
        c.circle(x, y, r, fill=0, stroke=1)
        d = r * 0.65
        c.line(x - d, y - d, x + d, y + d)
        c.line(x - d, y + d, x + d, y - d)

    elif head == "x_slash":
        c.setLineWidth(1.5)
        d = sz * 0.9
        c.line(x - d, y, x + d, y)
        c.line(x, y - d, x, y + d)

    elif head == "diamond":
        d = sz * 0.95
        p = c.beginPath()
        p.moveTo(x, y + d)
        p.lineTo(x + d * 0.65, y)
        p.lineTo(x, y - d)
        p.lineTo(x - d * 0.65, y)
        p.close()
        c.drawPath(p, fill=1, stroke=0)


def _draw_stem(c, x: float, y_note: float, direction: str):
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.9)
    sl = LS * 3.5
    off = 4.2
    if direction == "up":
        c.line(x + off, y_note, x + off, y_note + sl)
    else:
        c.line(x - off, y_note, x - off, y_note - sl)


def _draw_beam(c, x1: float, x2: float, y1: float, y2: float, direction: str):
    """Beam bar connecting two consecutive stems."""
    c.setStrokeColor(colors.black)
    c.setLineWidth(3.0)
    off = 4.2
    sl = LS * 3.5
    if direction == "up":
        c.line(x1 + off, y1 + sl, x2 + off, y2 + sl)
    else:
        c.line(x1 - off, y1 - sl, x2 - off, y2 - sl)


# ---------------------------------------------------------------------------
# Parse notation_json -> [measure][beat_index][list of drum keys]
# ---------------------------------------------------------------------------

def _parse_measures(notation_json: Dict, bpm: int) -> List[List[List[str]]]:
    result = []
    for measure in notation_json.get("measures", []):
        beats: List[List[str]] = [[] for _ in range(bpm)]
        for beat in measure.get("beats", []):
            bi = max(0, min(bpm - 1, int(beat.get("beat_number", 1)) - 1))
            for note in beat.get("notes", []):
                raw = str(note.get("drum_type", "")).strip().lower()
                if raw:
                    k = _norm(raw)
                    if k not in beats[bi]:
                        beats[bi].append(k)
        result.append(beats)
    return result


# ---------------------------------------------------------------------------
# Main PDF builder
# ---------------------------------------------------------------------------

def generate_notation_pdf(
    notation_id: str,
    notation_json: Dict[str, Any],
    tempo: int = 95,
    time_signature: str = "4/4",
    title: Optional[str] = None,
    created_at: Optional[str] = None,
) -> bytes:
    """Generate a PDF with a real percussion staff in standard musical notation (B&W)."""

    buf = io.BytesIO()
    page_w, page_h = landscape(A4)
    c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))

    doc_title = title or f"Drum Notation — {notation_id[:8]}"
    date_str = (created_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))[:19]

    try:
        bpm = int(time_signature.split("/")[0])
    except Exception:
        bpm = 4

    measures = _parse_measures(notation_json, bpm)

    # Demo fallback: standard rock beat
    if not measures:
        measures = []
        for _ in range(4):
            beat_list = []
            for b in range(bpm):
                notes = ["hi-hat"]
                if b == 0 or b == 2:
                    notes.append("kick")
                if b == 1 or b == 3:
                    notes.append("snare")
                beat_list.append(notes)
            measures.append(beat_list)

    # ---- Layout ----
    ML, MR, MT, MB = 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm
    staff_h = (STAFF_LINES - 1) * LS
    above   = LS * 7    # room above staff for crash stems
    below   = LS * 4    # room below staff for kick, foot hi-hat
    row_gap = 18.0
    row_h   = above + staff_h + below + row_gap

    # Header
    top = page_h - MT
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(colors.black)
    c.drawString(ML, top - 14, doc_title)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawString(ML, top - 26,
                 f"Tempo: {tempo} BPM  ·  Time Signature: {time_signature}  "
                 f"·  Measures: {len(measures)}  ·  Generated: {date_str}")

    content_top = top - 40
    MAX_PER_ROW = 8
    mpr     = min(MAX_PER_ROW, len(measures))
    use_w   = page_w - ML - MR
    PFX     = 38.0   # prefix width: clef + time sig
    beat_w  = max(14.0, (use_w - PFX) / (mpr * bpm))
    measure_w = beat_w * bpm

    mi  = 0   # measure index
    row = 0

    while mi < len(measures):
        y_bot = content_top - row * row_h - above

        # New page if out of space
        if y_bot - below < MB + 30:
            c.showPage()
            row   = 0
            y_bot = page_h - MT - above

        n  = min(mpr, len(measures) - mi)
        sw = PFX + measure_w * n

        # Staff lines
        _draw_staff(c, ML, y_bot, sw)

        # Percussion clef
        x_after = _draw_perc_clef(c, ML + 2, y_bot)

        # Time signature (first row only)
        if row == 0 and mi == 0:
            _draw_time_sig(c, x_after + 1, y_bot, time_signature)

        # Opening barline
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.7)
        c.line(ML + PFX, y_bot, ML + PFX, y_bot + staff_h)

        for ml in range(n):
            mabs      = mi + ml
            measure_x = ML + PFX + ml * measure_w

            # Measure number above staff
            c.setFont("Helvetica", 6)
            c.setFillColor(colors.HexColor("#888888"))
            c.drawCentredString(measure_x + measure_w / 2,
                                y_bot + staff_h + above * 0.88,
                                str(mabs + 1))

            beats_in   = measures[mabs]
            up_beats: List[int]   = []
            down_beats: List[int] = []

            for bi, notes in enumerate(beats_in):
                bx = measure_x + bi * beat_w + beat_w * 0.5

                if any(_info(k)["stem"] == "up"   for k in notes):
                    up_beats.append(bi)
                if any(_info(k)["stem"] == "down" for k in notes):
                    down_beats.append(bi)

                # Light subdivision tick on the middle line
                c.setStrokeColor(colors.HexColor("#CCCCCC"))
                c.setLineWidth(0.4)
                tick_y = _sy(y_bot, 2.0)
                c.line(bx, tick_y - 2, bx, tick_y + 2)

                # Beat number label
                c.setFont("Helvetica", 5)
                c.setFillColor(colors.HexColor("#AAAAAA"))
                c.drawCentredString(bx, y_bot - LS * 0.9, str(bi + 1))

                for dk in notes:
                    inf    = _info(dk)
                    sp     = inf["staff_pos"]
                    hd     = inf["head"]
                    st_dir = inf["stem"]
                    ny     = _sy(y_bot, sp)

                    if sp < 0 or sp > 4:
                        _draw_ledger(c, bx, y_bot, sp)

                    c.setFillColor(colors.black)
                    c.setStrokeColor(colors.black)
                    _draw_stem(c, bx, ny, st_dir)
                    _draw_head(c, bx, ny, hd)

            # Beam consecutive stem-up notes (hi-hats, cymbals)
            if len(up_beats) > 1:
                bxs = [measure_x + bi * beat_w + beat_w * 0.5 for bi in up_beats]

                def _up_y(bi: int) -> float:
                    sp = max(
                        (_info(k)["staff_pos"] for k in beats_in[bi]
                         if _info(k)["stem"] == "up"),
                        default=3.5,
                    )
                    return _sy(y_bot, sp)

                for i in range(len(bxs) - 1):
                    _draw_beam(c, bxs[i], bxs[i + 1],
                               _up_y(up_beats[i]), _up_y(up_beats[i + 1]), "up")

            # Beam consecutive stem-down notes (kick, floor tom)
            if len(down_beats) > 1:
                bxs = [measure_x + bi * beat_w + beat_w * 0.5 for bi in down_beats]

                def _dn_y(bi: int) -> float:
                    sp = min(
                        (_info(k)["staff_pos"] for k in beats_in[bi]
                         if _info(k)["stem"] == "down"),
                        default=-0.5,
                    )
                    return _sy(y_bot, sp)

                for i in range(len(bxs) - 1):
                    _draw_beam(c, bxs[i], bxs[i + 1],
                               _dn_y(down_beats[i]), _dn_y(down_beats[i + 1]), "down")

            # Closing barline
            is_last = (ml == n - 1) and (mabs == len(measures) - 1)
            _draw_barline(c, measure_x + measure_w, y_bot, final=is_last)

        mi  += n
        row += 1

    # ---- Notation key ----
    ky = MB + 24
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawString(ML, ky + 11, "Notation Key:")
    c.setFont("Helvetica", 7)
    items = [
        ("filled oval, stem down", "Kick / Floor Tom"),
        ("filled oval, stem up",   "Snare / Toms"),
        ("X head, stem up",        "Hi-Hat / Ride / Crash"),
        ("circle + X",             "Open Hi-Hat"),
        ("diamond",                "Ride Bell"),
    ]
    ex = ML
    for sym, desc in items:
        c.drawString(ex, ky, f"{sym}  =  {desc}")
        ex += 5.6 * cm

    c.setFont("Helvetica", 6)
    c.setFillColor(colors.HexColor("#BBBBBB"))
    c.drawCentredString(page_w / 2, MB * 0.4, "Cadence · Drum Notation Backend")

    c.save()
    return buf.getvalue()
