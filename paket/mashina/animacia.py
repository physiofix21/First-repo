"""Анимирани видеа 9:16 без камера и без платено AI видео.

Всеки кадър се рисува с Pillow (шрифтовете и цветовете на марката) и се
подава на ffmpeg. Сцените се сменят точно в паузите на гласа (silencedetect),
така че картината върви с думите.

Видове сцени (matrica.json → video → "sceni"):
  tekst     — думите изскачат една по една, ключовата в оранжево
  brojach   — брояч с кръгов индикатор (напр. 0 → 8 „часа на стола“)
  snimka    — снимка с бавно приближаване + етикети, които излизат по ред
  anatomia  — илюстрация + пулсиращ оранжев кръг + етикет
  klip      — истински видео кадри (стари/слаби се подобряват: шум, острота, цвят) + етикети
Накрая — крайна карта (банерът „snimka“ с призива).

Пример за сцена:
  {"vid": "tekst", "izr": [0], "redove": ["Седенето", "не е проблемът."], "akcent": "Седенето"}
  {"vid": "brojach", "izr": [2], "ot": 0, "do": 8, "edinica": "часа", "nadpis": "на стола"}
  {"vid": "snimka", "izr": [3], "dyal": [0.45, 1], "fail": "snimki/IMG_6800.jpg", "fokus": [0.5, 0.5],
   "etiketi": ["Тестове на движението", "Лечение още същия час"]}
  {"vid": "anatomia", "izr": [3], "dyal": [0, 0.45], "fail": "snimki/ai_grabnak.png", "tochka": [0.5, 0.62],
   "etiket": "Намираме причината"}
  {"vid": "klip", "izr": [4], "fail": "snimki/IMG_6789.mp4", "ot": 2.0, "fokus": [0.5, 0.5],
   "etiketi": ["Упражнение за вкъщи"]}
"izr" = кои изречения от glas_tekst покрива сцената; "dyal" = част от тях (0..1).
"""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import banneri as B
from .config import MashinaGreshka
from .video import _ffmpeg, nameri_glas, prodalzhitelnost

W, H, FPS = 1080, 1920, 30
GORE, DOLU = 260, 430          # безопасни зони за Reels/Stories
KRAI_SEK = 2.5


# ── време ────────────────────────────────────────────────────

def izrechenia(tekst: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", tekst.strip()) if s.strip()]


def pauzi(glas: Path) -> list[float]:
    """Средата на всяка пауза в гласа (ffmpeg silencedetect)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(glas), "-af", "silencedetect=noise=-32dB:d=0.12",
                        "-f", "null", "-"], capture_output=True, text=True)
    nachala = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    kraishta = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [(a + b) / 2 for a, b in zip(nachala, kraishta)]


def granici_izrechenia(tekst: str, glas_sek: float, pauzi_: list[float]) -> list[tuple[float, float]]:
    """Начало и край на всяко изречение: оценка по брой знаци, после залепена за най-близката пауза."""
    izr = izrechenia(tekst)
    znaci = [len(s) for s in izr]
    obshto = sum(znaci)
    granici, t = [0.0], 0.0
    for z in znaci[:-1]:
        t += glas_sek * z / obshto
        blizka = min(pauzi_, key=lambda p: abs(p - t), default=t)
        granici.append(blizka if abs(blizka - t) < 1.2 else t)
    granici.append(glas_sek)
    for i in range(1, len(granici)):            # ред и минимум 0.6 сек
        granici[i] = max(granici[i], granici[i - 1] + 0.6)
    return list(zip(granici[:-1], granici[1:]))


def subtitri_po_izrechenia(tekst: str, gr: list[tuple[float, float]], dumi: int = 4) -> list[dict]:
    rez = []
    for s, (a, b) in zip(izrechenia(tekst), gr):
        d = s.split()
        parcheta = [" ".join(d[i:i + dumi]) for i in range(0, len(d), dumi)]
        znaci = [len(p) + 2 for p in parcheta]
        t = a
        for p, z in zip(parcheta, znaci):
            dt = (b - a) * z / sum(znaci)
            rez.append({"ot": t, "do": t + dt, "tekst": p})
            t += dt
    return rez


# ── рисуване ─────────────────────────────────────────────────

def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _hex(c):
    return B._hex(c)


class Platno:
    def __init__(self, cfg, papka: Path):
        self.cfg = cfg
        self.m = cfg["marka"]
        self.papka = papka
        self._snimki: dict[str, Image.Image] = {}
        self.klipove: dict[int, "Klip"] = {}

    def snimka(self, fail: str, fokus=(0.5, 0.5)) -> Image.Image:
        """Снимката, изрязана до 9:16 с 15% запас за приближаването."""
        kluch = f"{fail}|{fokus}"
        if kluch not in self._snimki:
            pat = Path(fail)
            if not pat.is_absolute():
                pat = self.papka / pat
            if not pat.exists():
                raise MashinaGreshka(f"Липсва {pat}")
            im = ImageOps.exif_transpose(Image.open(pat)).convert("RGB")
            self._snimki[kluch] = ImageOps.fit(im, (int(W * 1.15), int(H * 1.15)), Image.LANCZOS, centering=tuple(fokus))
        return self._snimki[kluch]

    def ken_burns(self, fail, fokus, p: float) -> Image.Image:
        src = self.snimka(fail, fokus)
        z = 1.0 + 0.12 * _ease(p)                      # 100% → 112%
        cw, ch = src.width / 1.15 / z * 1.0, src.height / 1.15 / z
        cx, cy = src.width / 2, src.height / 2
        kutia = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        return src.resize((W, H), Image.BILINEAR, box=kutia)

    # текст
    def font(self, ime_kluch, razmer):
        return B._font(self.m[ime_kluch], razmer)

    def dumi_pop(self, im, redove, akcent, p, y0, razmer=118, cvqt=None, cvqt_a=None, centar=True):
        """Думите изскачат една по една (мащаб + прозрачност)."""
        d_list = []
        for r in redove:
            d_list.append(r.split())
        vsichki = sum(len(r) for r in d_list)
        akc = set((akcent or "").lower().split())
        font = self.font("shrift_zaglavie", razmer)
        cvqt = cvqt or "#FFFFFF"
        cvqt_a = cvqt_a or self.m["cvqt_akcent"]
        sloi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idx = 0
        y = y0
        for red in d_list:
            interval = font.getlength(" ")
            shir = sum(font.getlength(x) for x in red) + interval * (len(red) - 1)
            if shir > W - 2 * B.POLE:                     # смали, ако не се побира
                return self.dumi_pop(im, redove, akcent, p, y0, int(razmer * 0.88), cvqt, cvqt_a, centar)
            x = (W - shir) / 2 if centar else B.POLE
            for duma in red:
                start = idx / max(1, vsichki) * 0.55
                q = _ease((p - start) / 0.18)
                if q > 0:
                    boq = cvqt_a if duma.lower().strip(".,!?„“") in akc else cvqt
                    dw = int(font.getlength(duma)) + 20
                    dh = int(razmer * 1.3)
                    bukva = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
                    ImageDraw.Draw(bukva).text((10, 0), duma, font=font, fill=boq)
                    mashtab = 0.6 + 0.4 * q
                    bw, bh = max(1, int(dw * mashtab)), max(1, int(dh * mashtab))
                    bukva = bukva.resize((bw, bh), Image.BILINEAR)
                    if q < 1:
                        a = bukva.getchannel("A").point(lambda v, q=q: int(v * q))
                        bukva.putalpha(a)
                    sloi.alpha_composite(bukva, (int(x + (dw - bw) / 2 - 10), int(y + (dh - bh) / 2)))
                x += font.getlength(duma) + interval
                idx += 1
            y += int(razmer * 1.12)
        im.alpha_composite(sloi)
        return y

    def hapche(self, im, tekst, y, p_vlizane, cvqt_fon=None, cvqt_t="#FFFFFF", razmer=58, nomer=None):
        """Етикет, който се плъзга отдолу."""
        q = _ease(p_vlizane)
        if q <= 0:
            return
        font = self.font("shrift_tekst", razmer)
        tw = font.getlength(tekst)
        pad = int(razmer * 0.7)
        nw = int(razmer * 1.3) if nomer else 0
        w, h = int(tw + 2 * pad + nw), int(razmer * 1.9)
        sloi = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(sloi)
        d.rounded_rectangle((0, 0, w, h), radius=h // 2, fill=cvqt_fon or self.m["cvqt_osnoven"])
        if nomer:
            d.ellipse((pad // 2, (h - razmer * 1.1) // 2, pad // 2 + razmer * 1.1, (h + razmer * 1.1) // 2), fill=self.m["cvqt_akcent"])
            fn = self.font("shrift_zaglavie", int(razmer * 0.7))
            d.text((pad // 2 + razmer * 0.55 - fn.getlength(str(nomer)) / 2, (h - razmer * 0.8) / 2), str(nomer), font=fn, fill="#FFFFFF")
        d.text((pad + nw, (h - razmer * 1.25) / 2), tekst, font=font, fill=cvqt_t)
        if q < 1:
            sloi.putalpha(sloi.getchannel("A").point(lambda v: int(v * q)))
        im.alpha_composite(sloi, (int((W - w) / 2), int(y + (1 - q) * 60)))

    def subtitar(self, im, tekst):
        font = self.font("shrift_zaglavie", 58)
        redove = B._prenesi([(x, False) for x in tekst.split()], font, W - 220)
        y = H - DOLU - 40 - 84 * len(redove)
        sloi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(sloi)
        for red in redove:
            s = " ".join(x for x, _ in red)
            tw = font.getlength(s)
            x = (W - tw) / 2
            d.rounded_rectangle((x - 22, y - 8, x + tw + 22, y + 72), radius=18, fill=(0, 0, 0, 170))
            d.text((x, y), s, font=font, fill="#FFFFFF")
            y += 84
        im.alpha_composite(sloi)


class Klip:
    """Чете кадрите на клип последователно (ffmpeg → raw RGB), вече подобрени и изрязани до 9:16."""

    PODOBRI = "hqdn3d=2:1:3:3,unsharp=5:5:0.7:5:5:0,eq=contrast=1.06:saturation=1.15:gamma=1.02"

    def __init__(self, pat: Path, ot: float, sek: float, fokus=(0.5, 0.5), podobri=True):
        fx, fy = fokus
        vf = (f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy}" + ("," + self.PODOBRI if podobri else ""))
        self.proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{ot:.2f}", "-i", str(pat),
                                      "-t", f"{sek + 0.5:.2f}", "-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.n = -1
        self.posleden = Image.new("RGB", (W, H), "#000000")

    def kadar(self, nomer: int) -> Image.Image:
        while self.n < nomer:
            data = self.proc.stdout.read(W * H * 3)
            if len(data) < W * H * 3:
                break                      # клипът свърши → държим последния кадър
            self.posleden = Image.frombytes("RGB", (W, H), data)
            self.n += 1
        return self.posleden


# ── сцените ──────────────────────────────────────────────────

def _fon(cvqt):
    return Image.new("RGBA", (W, H), _hex(cvqt) + (255,))


def scena_tekst(pl: Platno, s, p, t):
    fon = s.get("fon", "osnoven")
    cvqt_fon = {"osnoven": pl.m["cvqt_osnoven"], "akcent": pl.m["cvqt_akcent"], "fon": pl.m["cvqt_fon"]}[fon]
    im = _fon(cvqt_fon)
    # леко „дишане“ на фона: голям полупрозрачен кръг в ъгъла (на отделен слой, за да се смеси)
    dekor = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    r = 520 + 40 * math.sin(t * 1.6)
    # декорът никога не е в цвета на акцента, за да не изяде оранжевата дума
    kr = (255, 255, 255, 22) if fon != "fon" else _hex(pl.m["cvqt_osnoven"]) + (18,)
    ImageDraw.Draw(dekor).ellipse((W - r * 0.9, -r * 0.4, W + r * 1.1, r * 1.6), fill=kr)
    im.alpha_composite(dekor)
    tekst_c = pl.m["cvqt_osnoven"] if fon == "fon" else "#FFFFFF"
    ak_c = pl.m["cvqt_akcent"] if fon != "akcent" else pl.m["cvqt_osnoven"]
    pl.dumi_pop(im, s["redove"], s.get("akcent"), p, int(H * 0.30), razmer=150, cvqt=tekst_c, cvqt_a=ak_c)
    return im


def scena_brojach(pl: Platno, s, p, t):
    im = _fon(pl.m["cvqt_osnoven"])
    d = ImageDraw.Draw(im)
    cx, cy, r = W // 2, int(H * 0.40), 300
    q = _ease(p / 0.7)
    pr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(pr).ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 50), width=26)
    im.alpha_composite(pr)
    d = ImageDraw.Draw(im)
    d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * q, fill=pl.m["cvqt_akcent"], width=26)
    stoinost = s["ot"] + (s["do"] - s["ot"]) * q
    chislo = str(int(round(stoinost)))
    f = pl.font("shrift_zaglavie", 260)
    d.text((cx - f.getlength(chislo) / 2, cy - 170), chislo, font=f, fill="#FFFFFF")
    fe = pl.font("shrift_tekst", 64)
    ed = s.get("edinica", "")
    d.text((cx - fe.getlength(ed) / 2, cy + 110), ed, font=fe, fill=(255, 255, 255, 200))
    if s.get("nadpis"):
        pl.dumi_pop(im, [s["nadpis"]], s.get("nadpis_akcent", s["nadpis"]), max(0, (p - 0.35) / 0.65), cy + r + 80, razmer=96)
    return im


def scena_snimka(pl: Platno, s, p, t):
    im = pl.ken_burns(s["fail"], s.get("fokus", (0.5, 0.5)), p).convert("RGBA")
    im.alpha_composite(B._gradient(W, H, 0.45, sila=200, nagore=True))
    im.alpha_composite(B._gradient(W, H, 0.55, sila=160))
    etiketi = s.get("etiketi", [])
    for i, e in enumerate(etiketi):
        start = 0.08 + i * (0.7 / max(1, len(etiketi)))
        pl.hapche(im, e, GORE + 60 + i * 140, (p - start) / 0.12, nomer=(i + 1) if s.get("nomera", True) and len(etiketi) > 1 else None)
    if s.get("zaglavie"):
        pl.dumi_pop(im, [s["zaglavie"]], s.get("akcent"), p, GORE + 40, razmer=100)
    return im


def scena_anatomia(pl: Platno, s, p, t):
    im = pl.ken_burns(s["fail"], s.get("fokus", (0.5, 0.5)), p * 0.8).convert("RGBA")
    tx, ty = s.get("tochka", (0.5, 0.6))
    cx, cy = int(W * tx), int(H * ty)
    puls = (math.sin(t * 5) + 1) / 2
    sloi = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sloi)
    for k, alfa, deb in ((1.0, 140, 14), (0.68, 220, 12)):
        r = int((170 + 45 * puls) * k)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=_hex(pl.m["cvqt_akcent"]) + (min(255, alfa + int(35 * puls)),), width=deb)
    im.alpha_composite(sloi.filter(ImageFilter.GaussianBlur(2)))
    if s.get("etiket"):
        pl.hapche(im, s["etiket"], GORE + 60, (p - 0.15) / 0.15, cvqt_fon=pl.m["cvqt_akcent"], razmer=58)
    return im


def scena_klip(pl: Platno, s, p, t):
    k = pl.klipove.get(id(s))
    if k is None:
        pat = Path(s["fail"])
        if not pat.is_absolute():
            pat = pl.papka / pat
        if not pat.exists():
            raise MashinaGreshka(f"Липсва клипът {pat}")
        k = pl.klipove[id(s)] = Klip(pat, float(s.get("ot", 0)), s["_sek"], s.get("fokus", (0.5, 0.5)), s.get("podobri", True))
    im = k.kadar(int(p * s["_sek"] * FPS)).convert("RGBA")
    im.alpha_composite(B._gradient(W, H, 0.40, sila=190, nagore=True))
    im.alpha_composite(B._gradient(W, H, 0.60, sila=150))
    etiketi = s.get("etiketi", [])
    for i, e in enumerate(etiketi):
        start = 0.08 + i * (0.7 / max(1, len(etiketi)))
        pl.hapche(im, e, GORE + 60 + i * 140, (p - start) / 0.12, nomer=(i + 1) if s.get("nomera", True) and len(etiketi) > 1 else None)
    return im


SCENI = {"klip": scena_klip, "tekst": scena_tekst, "brojach": scena_brojach, "snimka": scena_snimka, "anatomia": scena_anatomia}


# ── сглобяване ───────────────────────────────────────────────

def sglobi(v: dict, papka: Path, cfg, log=print) -> Path:
    if not v.get("sceni"):
        raise MashinaGreshka(f"Видео {v['kod']}: няма „sceni“ в матрицата.")
    glas = nameri_glas(papka, v["kod"])
    if not glas:
        raise MashinaGreshka(f"Видео {v['kod']}: няма глас video/{v['kod']}_glas.*")
    glas_sek = prodalzhitelnost(glas)
    gr = granici_izrechenia(v["glas_tekst"], glas_sek, pauzi(glas))
    subt = subtitri_po_izrechenia(v["glas_tekst"], gr)

    # времена на сцените (върху копие, за да не пишем служебни полета в матрицата)
    import copy
    v = copy.deepcopy(v)
    plan = []
    for s in v["sceni"]:
        a = gr[s["izr"][0]][0]
        b = gr[s["izr"][-1]][1]
        d0, d1 = s.get("dyal", (0, 1))
        plan.append((a + (b - a) * d0, a + (b - a) * d1, s))
    plan[0] = (0.0, plan[0][1], plan[0][2])
    for i in range(1, len(plan)):            # без дупки между сцените
        plan[i] = (plan[i - 1][1], plan[i][1], plan[i][2])
    obshto = glas_sek + 0.3 + KRAI_SEK
    krai_ot = glas_sek + 0.3
    plan[-1] = (plan[-1][0], krai_ot, plan[-1][2])
    for a, b, s in plan:
        s["_sek"] = b - a

    pl = Platno(cfg, papka)
    karta_pat = papka / "video" / "_rabota" / v["kod"] / "krai.png"
    karta_pat.parent.mkdir(parents=True, exist_ok=True)
    posledna = next((s.get("fail") for s in reversed(v["sceni"]) if s.get("vid") == "snimka"), None)
    B.napravi({"kod": v["kod"] + "-krai", "oformlenie": "snimka", "snimka": posledna or "",
               "fokus": next((s.get("fokus") for s in reversed(v["sceni"]) if s.get("vid") == "snimka"), None),
               "zaglavie": v.get("priziv") or cfg["marka"]["hapche_tekst"], "akcent": v.get("priziv_akcent", ""),
               "podzaglavie": cfg["biznes"].get("adres", "")}, "9x16", cfg, papka, karta_pat)
    karta = Image.open(karta_pat).convert("RGBA")

    izhod = papka / "video" / f"{v['kod']}.mp4"
    nem = papka / "video" / "_rabota" / v["kod"] / "anim.mp4"
    proc = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "20", "-pix_fmt", "yuv420p", str(nem)], stdin=subprocess.PIPE)
    n_kadri = int(obshto * FPS)
    for n in range(n_kadri):
        t = n / FPS
        if t >= krai_ot:
            q = _ease((t - krai_ot) / 0.35)
            z = 1.0 + 0.04 * ((t - krai_ot) / KRAI_SEK)
            kadar = karta.resize((int(W * z), int(H * z)), Image.BILINEAR).crop(
                (int((W * z - W) / 2), int((H * z - H) / 2), int((W * z - W) / 2) + W, int((H * z - H) / 2) + H))
            if q < 1:
                pred = SCENI[plan[-1][2]["vid"]](pl, plan[-1][2], 1.0, t)
                kadar = Image.blend(pred, kadar, q)
        else:
            a, b, s = next((x for x in plan if x[0] <= t < x[1]), plan[-1])
            p = (t - a) / max(0.01, b - a)
            kadar = SCENI[s["vid"]](pl, s, p, t)
            # кратко преливане между сцените
            i = plan.index((a, b, s))
            if i > 0 and t - a < 0.2:
                pa, pb, ps = plan[i - 1]
                pred = SCENI[ps["vid"]](pl, ps, 1.0, t)
                kadar = Image.blend(pred, kadar, _ease((t - a) / 0.2))
            for st in subt if s["vid"] != "tekst" else []:   # в текстовите сцени едрият текст стига
                if st["ot"] <= t < st["do"]:
                    pl.subtitar(kadar, st["tekst"])
                    break
        proc.stdin.write(kadar.convert("RGB").tobytes())
        if n % (FPS * 5) == 0:
            log(f"  {v['kod']}: {t:4.1f}/{obshto:.1f} сек")
    proc.stdin.close()
    for k in pl.klipove.values():
        k.proc.kill()
        k.proc.wait()
    if proc.wait() != 0:
        raise MashinaGreshka("ffmpeg не можа да запише анимацията")
    _ffmpeg("-i", str(nem), "-i", str(glas), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-af", f"apad=pad_dur={KRAI_SEK + 0.3}", "-t", f"{obshto:.2f}", "-movflags", "+faststart", str(izhod))
    _ffmpeg("-ss", "0.8", "-i", str(izhod), "-frames:v", "1", str(papka / "video" / f"{v['kod']}_korica.jpg"))
    return izhod
