#!/usr/bin/env python3
"""The Passport Page of a Country That Isn't There.

Pure-stdlib program (Python 3.13) that draws one invented passport spread
-- the Republic of Solmara -- as a 1024x1024 PNG and writes it to
/output/entry.png. Deterministic: same bytes on every run.
"""
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- canvas
class Canvas:
    """A plain RGB canvas with alpha-blended drawing primitives."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg * (w * h))

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set(self, x, y, col, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            if a >= 255:
                self.px[i:i + 3] = bytes(col)
            else:
                inv = 255 - a
                for k in range(3):
                    self.px[i + k] = (col[k] * a + self.px[i + k] * inv) // 255

    def rect(self, x, y, w, h, col, a=255):
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                self.set(xx, yy, col, a)

    def hline(self, x0, x1, y, col, a=255):
        for xx in range(max(0, x0), min(self.w, x1 + 1)):
            self.set(xx, y, col, a)

    def vline(self, x, y0, y1, col, a=255):
        for yy in range(max(0, y0), min(self.h, y1 + 1)):
            self.set(x, yy, col, a)

    def line(self, x0, y0, x1, y1, col, a=255):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, col, a)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, col, fill=True, a=255):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if fill:
                    if d2 <= r * r:
                        self.set(xx, yy, col, a)
                else:
                    if abs(d2 - r * r) <= r:
                        self.set(xx, yy, col, a)

    def ellipse(self, cx, cy, rx, ry, col, fill=True, a=255):
        for yy in range(cy - ry, cy + ry + 1):
            for xx in range(cx - rx, cx + rx + 1):
                v = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
                if fill:
                    if v <= 1.0:
                        self.set(xx, yy, col, a)
                else:
                    if abs(v - 1.0) <= 0.12:
                        self.set(xx, yy, col, a)

    def poly(self, pts, col, a=255):
        """Scanline fill of a simple polygon."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                for x in range(max(0, int(xs[i])), min(self.w, int(xs[i + 1]) + 1)):
                    self.set(x, y, col, a)

    def arc(self, cx, cy, r, a0, a1, col, a=255, step=0.02):
        import math
        t = a0
        while t <= a1:
            self.set(int(cx + r * math.cos(t)), int(cy + r * math.sin(t)), col, a)
            t += step

    def blit_rotated(self, src, cx, cy, angle_deg, alpha=255):
        """Composite a small canvas rotated about (cx, cy) onto this one."""
        import math
        th = math.radians(angle_deg)
        c, s = math.cos(th), math.sin(th)
        hw, hh = src.w // 2, src.h // 2
        for dy in range(-hh, hh + 1):
            for dx in range(-hw, hw + 1):
                sx = int(dx * c + dy * s) + hw
                sy = int(-dx * s + dy * c) + hh
                if 0 <= sx < src.w and 0 <= sy < src.h:
                    i = (sy * src.w + sx) * 3
                    r, g, b = src.px[i], src.px[i + 1], src.px[i + 2]
                    # source pixels drawn on white mean "no ink"; treat
                    # near-white as transparent.
                    if r > 245 and g > 245 and b > 245:
                        continue
                    self.set(cx + dx, cy + dy, (r, g, b), alpha)


# ---------------------------------------------------------------- PNG
def png_bytes(cv):
    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


# ---------------------------------------------------------------- font
# 5x7 bitmap font, one glyph per line: 7 rows of 5 bits ('1' = ink).
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10011", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "01010", "00100", "00100", "00100", "01010", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}

FONT.update({
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00010", "00100", "00100", "00100"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "01100", "01000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "'": ("00100", "00100", "00000", "00000", "00000", "00000", "00000"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "*": ("00000", "01010", "00100", "11111", "00100", "01010", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
})


def text_w(s, scale, spacing=1):
    return len(s) * (5 * scale + spacing) - spacing


def draw_text(cv, x, y, s, scale, col, spacing=1, a=255):
    """Draw uppercase text; unknown chars render as blank."""
    cx = x
    for ch in s.upper():
        g = FONT.get(ch, FONT[" "])
        for r in range(7):
            row = g[r]
            for c in range(5):
                if row[c] == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            cv.set(cx + c * scale + dx, y + r * scale + dy, col, a)
        cx += 5 * scale + spacing
    return cx - spacing


def draw_text_center(cv, cx, y, s, scale, col, spacing=1, a=255):
    draw_text(cv, cx - text_w(s, scale, spacing) // 2, y, s, scale, col, spacing, a)


def draw_text_right(cv, x, y, s, scale, col, spacing=1, a=255):
    draw_text(cv, x - text_w(s, scale, spacing), y, s, scale, col, spacing, a)


# ---------------------------------------------------------------- MRZ
def _mrz_val(ch):
    if "0" <= ch <= "9":
        return ord(ch) - 48
    if "A" <= ch <= "Z":
        return ord(ch) - 55
    return 0


def mrz_check(s):
    total = 0
    for i, ch in enumerate(s):
        total += _mrz_val(ch) * (7, 3, 1)[i % 3]
    return str(total % 10)


def mrz_lines():
    line1 = "P<SMRVELIS<<MARA<ELENA" + "<" * 22
    doc, nat = "SM0048217", "SMR"
    dob, sex, exp = "920414", "F", "340312"
    pers = "<" * 14
    line2 = (doc + mrz_check(doc) + nat + dob + mrz_check(dob) + sex + exp
             + mrz_check(exp) + pers)
    line2 += mrz_check(pers)
    line2 += mrz_check(line2[:10] + line2[13:20] + line2[21:28] + line2[28:43])
    assert len(line1) == 44 and len(line2) == 44, (len(line1), len(line2))
    return line1, line2


# ---------------------------------------------------------------- artwork
NAVY = (30, 58, 95)
INK = (32, 36, 42)
PAPER = (245, 239, 223)
PAPER2 = (238, 231, 210)
GOLD = (176, 132, 52)
TEAL = (38, 110, 108)
SKIN = (230, 180, 140)
SKIN_D = (206, 150, 110)
HAIR = (51, 36, 26)
JACKET = (39, 65, 86)
WHITE = (255, 255, 255)


def draw_emblem(cv, cx, cy, r):
    """Solmara's arms: a sun over three waves inside a ring."""
    cv.circle(cx, cy, r, NAVY, fill=False, a=255)
    cv.circle(cx, cy, r - 3, NAVY, fill=False, a=255)
    # sun
    cv.circle(cx, cy - r // 3, r // 3, GOLD, fill=True)
    import math
    for k in range(8):
        ang = k * math.pi / 4
        x0 = int(cx + (r // 3 + 2) * math.cos(ang))
        y0 = int(cy - r // 3 + (r // 3 + 2) * math.sin(ang))
        x1 = int(cx + (r // 3 + 9) * math.cos(ang))
        y1 = int(cy - r // 3 + (r // 3 + 9) * math.sin(ang))
        cv.line(x0, y0, x1, y1, GOLD)
    # waves
    for j, wy in enumerate((cy + r // 4, cy + r // 2)):
        for x in range(cx - r + 6, cx + r - 5):
            import math as _m
            y = wy + int(3 * _m.sin((x - cx) / 9.0 + j * 1.7))
            cv.set(x, y, TEAL, 220)


def draw_portrait(cv, x0, y0, w, h):
    """Flat-vector passport photograph of Mara Elena Velis."""
    cv.rect(x0, y0, w, h, (185, 196, 201))
    # soft backdrop oval
    cv.ellipse(x0 + w // 2, y0 + h // 2 - 6, w // 2 - 6, h // 2 - 4,
               (198, 208, 212), fill=True)
    cx = x0 + w // 2
    # shoulders / jacket
    cv.poly([(x0 + 8, y0 + h), (x0 + w - 8, y0 + h),
             (x0 + w - 16, y0 + h - 34), (cx + 26, y0 + h - 48),
             (cx - 26, y0 + h - 48), (x0 + 16, y0 + h - 34)], JACKET)
    # blouse
    cv.poly([(cx - 12, y0 + h - 50), (cx + 12, y0 + h - 50),
             (cx, y0 + h - 26)], WHITE)
    # neck
    cv.rect(cx - 11, y0 + h - 62, 22, 18, SKIN_D)
    # head
    cv.ellipse(cx, y0 + 62, 33, 41, SKIN, fill=True)
    # ears
    cv.ellipse(cx - 33, y0 + 62, 5, 9, SKIN, fill=True)
    cv.ellipse(cx + 33, y0 + 62, 5, 9, SKIN, fill=True)
    # hair: cap + side locks framing the face
    cv.poly([(cx - 36, y0 + 78), (cx - 38, y0 + 30), (cx - 24, y0 + 12),
             (cx, y0 + 8), (cx + 24, y0 + 12), (cx + 38, y0 + 30),
             (cx + 36, y0 + 78), (cx + 28, y0 + 46), (cx + 20, y0 + 30),
             (cx + 8, y0 + 24), (cx - 8, y0 + 24), (cx - 20, y0 + 30),
             (cx - 28, y0 + 46)], HAIR)
    # brows, eyes, nose, mouth
    cv.line(cx - 24, y0 + 52, cx - 10, y0 + 50, HAIR)
    cv.line(cx + 10, y0 + 50, cx + 24, y0 + 52, HAIR)
    for ex in (cx - 17, cx + 17):
        cv.ellipse(ex, y0 + 60, 4, 3, (28, 22, 18), fill=True)
        cv.circle(ex, y0 + 60, 1, WHITE, fill=True, a=200)
    cv.line(cx, y0 + 64, cx - 2, y0 + 76, SKIN_D)
    cv.line(cx - 2, y0 + 76, cx + 2, y0 + 76, SKIN_D)
    cv.line(cx - 9, y0 + 88, cx + 9, y0 + 88, (146, 74, 66))
    # laminate sheen
    for i in range(40):
        cv.set(x0 + 12 + i, y0 + h - 30 - i // 2, WHITE, 26)


def guilloche(cv, x0, y0, x1, y1, col, a=26):
    """Faint wavy security lines across a page region."""
    import math
    for k in range(6):
        yy = y0 + 14 + k * ((y1 - y0 - 28) // 5)
        for x in range(x0, x1):
            y = yy + int(2.5 * math.sin(x / 14.0 + k * 1.3))
            cv.set(x, y, col, a)


# ---------------------------------------------------------------- stamps
def make_stamp(country, action, date, ink):
    """A small ink stamp on a white buffer, ready to be rotated on."""
    cv = Canvas(230, 100, WHITE)
    cv.rect(4, 4, 222, 92, ink, a=255)          # outer frame (thin via overlay)
    cv.rect(7, 7, 216, 86, WHITE)
    cv.rect(10, 10, 210, 80, ink, a=255)
    cv.rect(13, 13, 204, 74, WHITE)
    draw_text_center(cv, 115, 20, country, 2, ink, spacing=0)
    draw_text_center(cv, 115, 46, action, 1, ink, spacing=1)
    draw_text_center(cv, 115, 64, date, 2, ink, spacing=0)
    return cv


def draw_visa_sticker(cv, x0, y0, x1, y1):
    cv.rect(x0, y0, x1 - x0, y1 - y0, (226, 232, 238))
    cv.rect(x0, y0, x1 - x0, y1 - y0, NAVY, a=255)
    cv.rect(x0 + 3, y0 + 3, x1 - x0 - 6, y1 - y0 - 6, NAVY, a=255)
    # inner frame lines only (keep the fill): redraw fill inside frame
    cv.rect(x0 + 4, y0 + 4, x1 - x0 - 8, y1 - y0 - 8, (226, 232, 238))
    draw_text(cv, x0 + 16, y0 + 12, "VISA", 3, NAVY)
    draw_text(cv, x0 + 16, y0 + 44, "TALMERIA", 2, NAVY)
    draw_text(cv, x0 + 16, y0 + 74, "MULTIPLE ENTRY - 90 DAYS", 1, INK)
    draw_text(cv, x0 + 16, y0 + 92, "No. TV-8841-22", 1, INK)
    draw_text(cv, x0 + 16, y0 + 110, "VALID 03 SEP 2024 - 03 MAR 2025", 1, INK)
    draw_text(cv, x0 + 16, y0 + 134, "CONDITION: HOLDER MAY NOT TAKE", 1, INK)
    draw_text(cv, x0 + 16, y0 + 150, "PAID EMPLOYMENT IN TALMERIA", 1, INK)
    draw_text(cv, x0 + 16, y0 + 172, "FEE PAID - 45 S", 1, (169, 50, 38))
    # red fee seal
    cv.circle(x1 - 52, y0 + 52, 34, (169, 50, 38), fill=False, a=200)
    cv.circle(x1 - 52, y0 + 52, 29, (169, 50, 38), fill=False, a=200)
    draw_text_center(cv, x1 - 52, y0 + 38, "45 S", 2, (169, 50, 38), spacing=0)
    draw_text_center(cv, x1 - 52, y0 + 62, "PAID", 1, (169, 50, 38), spacing=1)


def draw_island_map(cv, x0, y0):
    """A small chart of Solmara with Porto Lume marked."""
    cv.rect(x0, y0, 210, 150, (214, 228, 232))
    cv.rect(x0, y0, 210, 150, NAVY, a=255)
    # sea lines
    for i in range(5):
        cv.line(x0 + 8, y0 + 22 + i * 26, x0 + 202, y0 + 22 + i * 26, TEAL, a=60)
    # island
    cv.poly([(x0 + 60, y0 + 40), (x0 + 130, y0 + 34), (x0 + 168, y0 + 66),
             (x0 + 150, y0 + 108), (x0 + 96, y0 + 118), (x0 + 58, y0 + 96),
             (x0 + 48, y0 + 62)], (222, 206, 160))
    cv.poly([(x0 + 60, y0 + 40), (x0 + 130, y0 + 34), (x0 + 168, y0 + 66),
             (x0 + 150, y0 + 108), (x0 + 96, y0 + 118), (x0 + 58, y0 + 96),
             (x0 + 48, y0 + 62)], TEAL, a=255)  # outline pass below
    # redraw island fill over the outline pass
    cv.poly([(x0 + 62, y0 + 42), (x0 + 128, y0 + 37), (x0 + 164, y0 + 66),
             (x0 + 148, y0 + 105), (x0 + 97, y0 + 115), (x0 + 61, y0 + 94),
             (x0 + 51, y0 + 62)], (222, 206, 160))
    # Porto Lume dot + label (label sits fully on the island, under the dot)
    cv.circle(x0 + 118, y0 + 72, 4, (169, 50, 38), fill=True)
    cv.circle(x0 + 118, y0 + 72, 7, (169, 50, 38), fill=False, a=200)
    draw_text(cv, x0 + 78, y0 + 92, "PORTO LUME", 1, INK)
    draw_text_center(cv, x0 + 105, y0 + 126, "SOLMARA", 1, NAVY)


# ---------------------------------------------------------------- spread
def field(cv, x, y, label, value, vscale=2):
    draw_text(cv, x, y, label, 1, (110, 96, 70))
    draw_text(cv, x, y + 16, value, vscale, INK)


def build():
    cv = Canvas(W, H, PAPER)
    # page tint + gutter
    cv.rect(516, 0, 8, H, (120, 108, 84), a=90)
    cv.rect(0, 0, W, H, (0, 0, 0), a=0)
    guilloche(cv, 8, 80, 500, 860, NAVY)
    guilloche(cv, 524, 280, 1016, 640, NAVY)

    # ---- left page: data page
    cv.rect(0, 0, 508, 74, NAVY)
    draw_text_center(cv, 254, 16, "REPUBLIC OF SOLMARA", 3, WHITE, spacing=1)
    draw_text_center(cv, 254, 46, "PASSPORT", 2, (214, 196, 130), spacing=2)
    draw_emblem(cv, 66, 118, 30)
    draw_text(cv, 112, 96, "TYPE", 1, (110, 96, 70))
    draw_text(cv, 112, 112, "P", 2, INK)
    draw_text(cv, 170, 96, "CODE", 1, (110, 96, 70))
    draw_text(cv, 170, 112, "SMR", 2, INK)
    draw_text(cv, 250, 96, "PASSPORT No.", 1, (110, 96, 70))
    draw_text(cv, 250, 112, "SM-0048217", 2, INK)
    # portrait
    cv.rect(26, 148, 144, 164, NAVY)
    draw_portrait(cv, 30, 152, 136, 156)
    # fields beside portrait
    field(cv, 192, 150, "SURNAME", "VELIS")
    field(cv, 192, 198, "GIVEN NAMES", "MARA ELENA")
    field(cv, 192, 246, "NATIONALITY", "SOLMARAN")
    field(cv, 192, 294, "DATE OF BIRTH", "14 APR 1992")
    # fields below
    field(cv, 28, 336, "PLACE OF BIRTH", "PORTO LUME")
    field(cv, 28, 384, "SEX", "F")
    field(cv, 120, 384, "DATE OF ISSUE", "12 MAR 2024")
    field(cv, 330, 384, "DATE OF EXPIRY", "12 MAR 2034")
    field(cv, 28, 432, "AUTHORITY", "MINISTRY OF THE INTERIOR")
    draw_text(cv, 28, 472, "PORTO LUME", 2, INK)
    field(cv, 28, 516, "REMARKS", "NONE")
    # holder's signature
    cv.line(28, 596, 240, 596, INK)
    for i, (dx, dy) in enumerate([(0, 0), (14, -8), (30, 4), (46, -6), (62, 3),
                                  (80, -5), (96, 2), (112, -7), (128, 1),
                                  (146, -4), (162, 0), (180, -3), (196, 0)]):
        if i:
            px, py = [(0, 0), (14, -8), (30, 4), (46, -6), (62, 3),
                      (80, -5), (96, 2), (112, -7), (128, 1),
                      (146, -4), (162, 0), (180, -3), (196, 0)][i - 1]
            cv.line(34 + px, 590 + py, 34 + dx, 590 + dy, INK)
    draw_text(cv, 28, 604, "HOLDER'S SIGNATURE", 1, (110, 96, 70))
    # ministry seal
    cv.circle(420, 560, 42, NAVY, fill=False, a=220)
    cv.circle(420, 560, 36, NAVY, fill=False, a=220)
    draw_text_center(cv, 420, 540, "SOLMARA", 1, NAVY, spacing=0)
    draw_text_center(cv, 420, 556, "PORTO", 1, NAVY, spacing=0)
    draw_text_center(cv, 420, 572, "LUME", 1, NAVY, spacing=0)
    # emergency contact fills the data page's lower half
    field(cv, 28, 648, "EMERGENCY CONTACT", "ANA VELIS")
    draw_text(cv, 28, 688, "14 RIVA STREET, PORTO LUME", 1, INK)
    draw_text(cv, 28, 704, "TEL. +382 44 210 987", 1, INK)
    draw_text(cv, 28, 740, "THIS PASSPORT REMAINS THE PROPERTY", 1, (110, 96, 70))
    draw_text(cv, 28, 756, "OF THE REPUBLIC OF SOLMARA.", 1, (110, 96, 70))
    # MRZ band
    cv.rect(0, 872, 508, 152, PAPER2)
    cv.hline(0, 507, 872, NAVY)
    line1, line2 = mrz_lines()
    draw_text(cv, 34, 900, line1, 2, INK, spacing=0)
    draw_text(cv, 34, 936, line2, 2, INK, spacing=0)

    # ---- right page: visas
    draw_text_center(cv, 770, 22, "VISAS", 3, NAVY, spacing=2)
    draw_text_center(cv, 770, 50, "VIZAT", 1, (110, 96, 70), spacing=2)
    draw_visa_sticker(cv, 540, 76, 1000, 268)
    # travel stamps (all after the 12 MAR 2024 issue date)
    stamps = [
        ("NORDVELL", "ARRIVED", "08 JUN 2024", (44, 79, 158), 655, 330, -7),
        ("NORDVELL", "DEPARTED", "21 JUN 2024", (44, 79, 158), 885, 330, 6),
        ("TALMERIA", "ARRIVED", "03 SEP 2024", (169, 50, 38), 655, 452, -4),
        ("OSTKOVIA", "ARRIVED", "11 JAN 2025", (94, 58, 125), 885, 452, 8),
        ("OSTKOVIA", "DEPARTED", "28 JAN 2025", (94, 58, 125), 770, 574, -6),
    ]
    for country, action, date, ink, cx, cy, ang in stamps:
        cv.blit_rotated(make_stamp(country, action, date, ink), cx, cy, ang, 165)
    # observations
    field(cv, 540, 660, "OBSERVATIONS", "BEARER ENTITLED TO CONSULAR")
    draw_text(cv, 540, 700, "PROTECTION OF SOLMARA ABROAD.", 1, INK)
    # island chart + endorsements
    draw_island_map(cv, 540, 730)
    cv.rect(780, 730, 220, 150, PAPER2)
    cv.rect(780, 730, 220, 150, NAVY, a=255)
    cv.rect(784, 734, 212, 142, PAPER2)
    draw_text(cv, 796, 748, "ENDORSEMENTS", 1, NAVY)
    draw_text(cv, 796, 776, "NONE", 2, INK)
    cv.hline(796, 984, 820, INK)
    cv.hline(796, 984, 848, INK)
    # outer border + gutter shadow
    cv.rect(0, 0, W, 3, NAVY)
    cv.rect(0, H - 3, W, 3, NAVY)
    cv.rect(0, 0, 3, H, NAVY)
    cv.rect(W - 3, 0, 3, H, NAVY)
    cv.rect(506, 0, 3, H, (90, 80, 60), a=110)
    cv.rect(515, 0, 3, H, (90, 80, 60), a=110)
    return cv


def main():
    cv = build()
    data = png_bytes(cv)
    os.makedirs("/output", exist_ok=True)
    with open("/output/entry.png", "wb") as f:
        f.write(data)
    import hashlib
    print("wrote /output/entry.png", len(data), "bytes",
          "sha256", hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
