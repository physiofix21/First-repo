"""Банери с кирилица, буква по буква.

Машината слага текста сама, с шрифта на марката. AI-ят (KIE/Magnific) прави
само снимката/фона, без текст. Така буквите никога не излизат изкривени.

5 оформления по ъгъл (като Canva шаблоните):
  snimka        — оферта: снимка на цял екран, хук горе, хапче „Запиши час“
  bolka         — болка: снимка горе, крем панел с хука долу
  dokazatelstvo — доказателство: голямо „5.0 ★“ + брой отзиви
  mehanizam     — механизъм: „какво става на прегледа“ в 3 стъпки
  sravnenie     — сравнение: ✕ мит / ✓ факт
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .config import FONTOVE, MashinaGreshka

FORMATI = {"1x1": (1080, 1080), "4x5": (1080, 1350), "9x16": (1080, 1920)}
# безопасни зони за 9:16 (Reels/Stories): горе и долу има интерфейс
BEZOPASNO = {"1x1": (60, 60), "4x5": (70, 70), "9x16": (260, 430)}
POLE = 72  # странично поле


def _font(ime: str, razmer: int) -> ImageFont.FreeTypeFont:
    pat = FONTOVE / ime
    if not pat.exists():
        raise MashinaGreshka(f"Липсва шрифт {pat}")
    return ImageFont.truetype(str(pat), razmer)


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _cover(snimka: Path | None, w: int, h: int, fon: str) -> Image.Image:
    if snimka and Path(snimka).exists():
        im = Image.open(snimka)
        im = ImageOps.exif_transpose(im).convert("RGB")
        return ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(0.5, 0.4))
    # без снимка: фон на марката с мек градиент
    baza = Image.new("RGB", (w, h), _hex(fon))
    return baza


def _gradient(w: int, h: int, ot: float, cvqt=(0, 0, 0), sila=220, nagore=False) -> Image.Image:
    """Прозрачен→тъмен градиент от височина ot (0..1) до края."""
    g = Image.new("L", (1, h), 0)
    start = int(h * ot)
    for y in range(h):
        if nagore:
            t = max(0.0, (start - y) / max(1, start))
        else:
            t = max(0.0, (y - start) / max(1, h - start))
        g.putpixel((0, y), int(sila * min(1.0, t) ** 1.2))
    maska = g.resize((w, h))
    sloi = Image.new("RGBA", (w, h), cvqt + (0,))
    sloi.putalpha(maska)
    return sloi


def _dumi_s_akcent(tekst: str, akcent: str | None) -> list[tuple[str, bool]]:
    dumi = tekst.split()
    marki = [False] * len(dumi)
    if akcent:
        ad = akcent.lower().split()
        for i in range(len(dumi) - len(ad) + 1):
            if [d.lower().strip(",.!?:;„“\"") for d in dumi[i:i + len(ad)]] == [a.strip(",.!?:;„“\"") for a in ad]:
                for j in range(i, i + len(ad)):
                    marki[j] = True
                break
    return list(zip(dumi, marki))


def _prenesi(dumi, font, shirina):
    redove, red, w_red = [], [], 0
    interval = font.getlength(" ")
    for d, a in dumi:
        wd = font.getlength(d)
        if red and w_red + interval + wd > shirina:
            redove.append(red)
            red, w_red = [], 0
        red.append((d, a))
        w_red += (interval if len(red) > 1 else 0) + wd
    if red:
        redove.append(red)
    return redove


def _pishi_zaglavie(d: ImageDraw.ImageDraw, tekst, akcent, kutia, shrift, cvqt, cvqt_akcent,
                    maks=120, minimum=44, podravni="lqvo", otdolu=False, centar_v=False) -> int:
    """Вписва заглавието в кутията (x, y, w, h), намалява размера, докато се събере.
    Връща y след последния ред."""
    x, y, w, h = kutia
    dumi = _dumi_s_akcent(tekst, akcent)
    razmer = maks
    while razmer >= minimum:
        font = _font(shrift, razmer)
        redove = _prenesi(dumi, font, w)
        vis_red = int(razmer * 1.08)
        obshto = vis_red * len(redove)
        nai_dalga = max(font.getlength(" ".join(dd for dd, _ in r)) for r in redove)
        if obshto <= h and nai_dalga <= w and len(redove) <= 4:
            break
        razmer -= 4
    font = _font(shrift, razmer)
    redove = _prenesi(dumi, font, w)
    vis_red = int(razmer * 1.08)
    if otdolu:
        y = y + h - vis_red * len(redove)
    elif centar_v:
        y = y + (h - vis_red * len(redove)) // 2
    interval = font.getlength(" ")
    for red in redove:
        shir = sum(font.getlength(dd) for dd, _ in red) + interval * (len(red) - 1)
        cx = x + (w - shir) / 2 if podravni == "centar" else x
        for dd, a in red:
            d.text((cx, y), dd, font=font, fill=cvqt_akcent if a else cvqt)
            cx += font.getlength(dd) + interval
        y += vis_red
    return y


def _pishi_tekst(d, tekst, kutia, shrift, razmer, cvqt, podravni="lqvo", red_k=1.3) -> int:
    x, y, w, _ = kutia
    font = _font(shrift, razmer)
    for red in _prenesi([(t, False) for t in tekst.split()], font, w):
        s = " ".join(t for t, _ in red)
        cx = x + (w - font.getlength(s)) / 2 if podravni == "centar" else x
        d.text((cx, y), s, font=font, fill=cvqt)
        y += int(razmer * red_k)
    return y


def _hapche(d, tekst, x, y, shrift, cvqt_fon, cvqt_tekst, razmer=44, centar=False, shirina_platno=None) -> tuple[int, int]:
    font = _font(shrift, razmer)
    tw = font.getlength(tekst)
    pad_x, pad_y = int(razmer * 0.8), int(razmer * 0.45)
    w, h = int(tw + 2 * pad_x), int(razmer + 2 * pad_y)
    if centar and shirina_platno:
        x = (shirina_platno - w) // 2
    d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=cvqt_fon)
    d.text((x + pad_x, y + pad_y - razmer * 0.08), tekst, font=font, fill=cvqt_tekst)
    return w, h


HAPCHE_VIS = {44: 84, 40: 76}


def _hapche_y(h, fmt, razmer=44):
    return h - BEZOPASNO[fmt][1] - HAPCHE_VIS.get(razmer, int(razmer * 1.9))


def _logo(d, ime, x, y, cvqt, cfg):
    font = _font(cfg.get("marka", "shrift_zaglavie"), 34)
    d.text((x, y), ime, font=font, fill=cvqt)


def _zvezda(d, cx, cy, r, cvqt):
    import math
    tochki = []
    for i in range(10):
        ugal = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        tochki.append((cx + rr * math.cos(ugal), cy - rr * math.sin(ugal)))
    d.polygon(tochki, fill=cvqt)


def _krastche(d, cx, cy, r, cvqt, debel=12):
    d.line((cx - r, cy - r, cx + r, cy + r), fill=cvqt, width=debel)
    d.line((cx - r, cy + r, cx + r, cy - r), fill=cvqt, width=debel)


def _otmetka(d, cx, cy, r, cvqt, debel=12):
    d.line((cx - r, cy, cx - r * 0.25, cy + r * 0.7, cx + r, cy - r * 0.7), fill=cvqt, width=debel, joint="curve")


# ── оформления ───────────────────────────────────────────────

def _snimka(b, fmt, cfg, im):
    w, h = im.size
    gore, dolu = BEZOPASNO[fmt]
    m = cfg["marka"]
    im = im.convert("RGBA")
    im.alpha_composite(Image.new("RGBA", (w, h), (0, 0, 0, 60)))
    im.alpha_composite(_gradient(w, h, 0.62, sila=245, nagore=True))
    im.alpha_composite(_gradient(w, h, 0.65, sila=190))
    d = ImageDraw.Draw(im)
    _logo(d, cfg["biznes"]["ime"], POLE, gore, m["cvqt_tekst_svetal"], cfg)
    y = _pishi_zaglavie(d, b["zaglavie"], b.get("akcent"), (POLE, gore + 70, w - 2 * POLE, int(h * 0.34)),
                        m["shrift_zaglavie"], m["cvqt_tekst_svetal"], m["cvqt_akcent"])
    if b.get("podzaglavie"):
        _pishi_tekst(d, b["podzaglavie"], (POLE, y + 14, w - 2 * POLE, 200), m["shrift_tekst"], 40, m["cvqt_tekst_svetal"])
    _hapche(d, b.get("hapche") or m["hapche_tekst"], POLE, _hapche_y(h, fmt), m["shrift_tekst"], m["cvqt_akcent"], "#FFFFFF")
    return im


def _bolka(b, fmt, cfg, im):
    w, h = im.size
    gore, dolu = BEZOPASNO[fmt]
    m = cfg["marka"]
    panel_y = int(h * {"1x1": 0.50, "4x5": 0.54, "9x16": 0.46}[fmt])
    platno = Image.new("RGBA", (w, h), _hex(m["cvqt_fon"]) + (255,))
    snimka = ImageOps.fit(im.convert("RGB"), (w, panel_y), Image.LANCZOS, centering=(0.5, 0.35))
    platno.paste(snimka, (0, 0))
    d = ImageDraw.Draw(platno)
    d.rectangle((0, panel_y - 10, w, panel_y), fill=m["cvqt_akcent"])
    _logo(d, cfg["biznes"]["ime"], POLE, gore, m["cvqt_tekst_svetal"], cfg)
    hy = _hapche_y(h, fmt, 40)
    pod = 110 if b.get("podzaglavie") else 0
    vis_panel = hy - (panel_y + 44) - pod - 36
    y = _pishi_zaglavie(d, b["zaglavie"], b.get("akcent"), (POLE, panel_y + 44, w - 2 * POLE, vis_panel),
                        m["shrift_zaglavie"], m["cvqt_osnoven"], m["cvqt_akcent"], maks=100)
    if b.get("podzaglavie"):
        _pishi_tekst(d, b["podzaglavie"], (POLE, y + 8, w - 2 * POLE, 100), m["shrift_tekst"], 36, m["cvqt_osnoven"])
    _hapche(d, b.get("hapche") or m["hapche_tekst"], POLE, hy, m["shrift_tekst"], m["cvqt_osnoven"], "#FFFFFF", razmer=40)
    return platno


def _dokazatelstvo(b, fmt, cfg, im):
    w, h = im.size
    gore, dolu = BEZOPASNO[fmt]
    m = cfg["marka"]
    dk = cfg.data.get("dokazatelstva", {})
    im = im.convert("RGBA").filter(ImageFilter.GaussianBlur(3))
    tamno = Image.new("RGBA", (w, h), _hex(m["cvqt_osnoven"]) + (150,))
    im.alpha_composite(tamno)
    d = ImageDraw.Draw(im)
    _logo(d, cfg["biznes"]["ime"], POLE, gore, m["cvqt_tekst_svetal"], cfg)
    # карта
    kx, kw = POLE, w - 2 * POLE
    ky = gore + 90 if fmt == "1x1" else int(h * 0.26)
    kh = 360 if fmt == "1x1" else 420
    d.rounded_rectangle((kx, ky, kx + kw, ky + kh), radius=40, fill=m["cvqt_fon"])
    ocenka = b.get("ocenka") or dk.get("google_ocenka", "5.0")
    font_o = _font(m["shrift_zaglavie"], 190)
    d.text((kx + 60, ky + 50), ocenka, font=font_o, fill=m["cvqt_osnoven"])
    ox = kx + 60 + font_o.getlength(ocenka) + 40
    for i in range(5):
        _zvezda(d, ox + 30 + i * 70, ky + 150, 30, m["cvqt_akcent"])
    _pishi_tekst(d, b.get("podzaglavie") or f"{dk.get('google_otzivi', '')} отзива в Google",
                 (ox, ky + 200, kx + kw - ox - 40, 120), m["shrift_tekst"], 40, m["cvqt_osnoven"])
    hy = _hapche_y(h, fmt)
    _pishi_zaglavie(d, b["zaglavie"], b.get("akcent"), (POLE, ky + kh + 50, w - 2 * POLE, hy - (ky + kh + 50) - 40),
                    m["shrift_zaglavie"], m["cvqt_tekst_svetal"], m["cvqt_akcent"], maks=92)
    _hapche(d, b.get("hapche") or m["hapche_tekst"], POLE, hy, m["shrift_tekst"], m["cvqt_akcent"], "#FFFFFF")
    return im


def _mehanizam(b, fmt, cfg, im):
    w, h = im.size
    gore, dolu = BEZOPASNO[fmt]
    m = cfg["marka"]
    platno = Image.new("RGBA", (w, h), _hex(m["cvqt_fon"]) + (255,))
    d = ImageDraw.Draw(platno)
    _logo(d, cfg["biznes"]["ime"], POLE, gore, m["cvqt_osnoven"], cfg)
    y = _pishi_zaglavie(d, b["zaglavie"], b.get("akcent"), (POLE, gore + 70, w - 2 * POLE, int(h * 0.22)),
                        m["shrift_zaglavie"], m["cvqt_osnoven"], m["cvqt_akcent"], maks=90)
    stapki = (b.get("stapki") or [])[:3]
    hy = _hapche_y(h, fmt, 40)
    sv = hy - 40 - 92 * len(stapki) - 40 - (y + 30)
    if sv >= 160:
        snimka = ImageOps.fit(im.convert("RGB"), (w - 2 * POLE, sv), Image.LANCZOS, centering=(0.5, 0.4))
        maska = Image.new("L", snimka.size, 0)
        ImageDraw.Draw(maska).rounded_rectangle((0, 0) + snimka.size, radius=36, fill=255)
        platno.paste(snimka, (POLE, y + 30), maska)
        y = y + 30 + sv + 40
    else:
        y += 40
    font_n = _font(m["shrift_zaglavie"], 44)
    for i, s in enumerate(stapki, 1):
        d.ellipse((POLE, y, POLE + 64, y + 64), fill=m["cvqt_akcent"])
        d.text((POLE + 32 - font_n.getlength(str(i)) / 2, y + 4), str(i), font=font_n, fill="#FFFFFF")
        _pishi_tekst(d, s, (POLE + 90, y + 8, w - 2 * POLE - 90, 80), m["shrift_tekst"], 40, m["cvqt_osnoven"])
        y += 92
    _hapche(d, b.get("hapche") or m["hapche_tekst"], POLE, hy, m["shrift_tekst"], m["cvqt_osnoven"], "#FFFFFF", razmer=40)
    return platno


def _sravnenie(b, fmt, cfg, im):
    w, h = im.size
    gore, dolu = BEZOPASNO[fmt]
    m = cfg["marka"]
    platno = Image.new("RGBA", (w, h), _hex(m["cvqt_fon"]) + (255,))
    d = ImageDraw.Draw(platno)
    _logo(d, cfg["biznes"]["ime"], POLE, gore, m["cvqt_osnoven"], cfg)
    y = _pishi_zaglavie(d, b["zaglavie"], b.get("akcent"), (POLE, gore + 70, w - 2 * POLE, int(h * 0.2)),
                        m["shrift_zaglavie"], m["cvqt_osnoven"], m["cvqt_akcent"], maks=88)
    y += 30
    hy = _hapche_y(h, fmt, 40)
    dolna_granica = hy - 34
    vis = (dolna_granica - y - 30) // 2
    for i, (kluch, cvqt_fon, cvqt_t, znak) in enumerate([
        ("mit", "#FFFFFF", m["cvqt_osnoven"], "x"),
        ("fakt", m["cvqt_osnoven"], "#FFFFFF", "v"),
    ]):
        ky = y + i * (vis + 30)
        d.rounded_rectangle((POLE, ky, w - POLE, ky + vis), radius=36, fill=cvqt_fon)
        cx, cy = POLE + 80, ky + vis // 2
        if znak == "x":
            _krastche(d, cx, cy, 30, "#C8372D")
        else:
            _otmetka(d, cx, cy, 34, m["cvqt_akcent"])
        tekst = b.get(kluch) or ""
        _pishi_zaglavie(d, tekst, None, (POLE + 150, ky + 40, w - 2 * POLE - 190, vis - 80),
                        m["shrift_tekst"], cvqt_t, cvqt_t, maks=56, minimum=30, centar_v=True)
    _hapche(d, b.get("hapche") or m["hapche_tekst"], POLE, hy, m["shrift_tekst"], m["cvqt_akcent"], "#FFFFFF", razmer=40)
    return platno


OFORMLENIA = {
    "snimka": _snimka,
    "bolka": _bolka,
    "dokazatelstvo": _dokazatelstvo,
    "mehanizam": _mehanizam,
    "sravnenie": _sravnenie,
}
# кой ъгъл с кое оформление върви по подразбиране
AGAL_KAM_OFORMLENIE = {
    "оферта": "snimka", "болка": "bolka", "доказателство": "dokazatelstvo",
    "механизъм": "mehanizam", "сравнение": "sravnenie",
}


def napravi(b: dict, fmt: str, cfg, papka_snimki: Path, izhod: Path) -> Path:
    if fmt not in FORMATI:
        raise MashinaGreshka(f"Непознат формат {fmt}. Има: {', '.join(FORMATI)}")
    oformlenie = b.get("oformlenie", "snimka")
    if oformlenie not in OFORMLENIA:
        raise MashinaGreshka(f"Банер {b.get('kod')}: непознато оформление „{oformlenie}“. Има: {', '.join(OFORMLENIA)}")
    w, h = FORMATI[fmt]
    snimka = None
    if b.get("snimka"):
        snimka = Path(b["snimka"])
        if not snimka.is_absolute():
            snimka = papka_snimki / snimka
        if not snimka.exists():
            raise MashinaGreshka(f"Банер {b.get('kod')}: няма снимка {snimka}")
    im = _cover(snimka, w, h, cfg["marka"]["cvqt_osnoven"])
    gotov = OFORMLENIA[oformlenie](b, fmt, cfg, im).convert("RGB")
    izhod.parent.mkdir(parents=True, exist_ok=True)
    gotov.save(izhod, "PNG", optimize=True)
    return izhod
