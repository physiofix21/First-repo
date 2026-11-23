"""Видеата 9:16: хук + тяло + призив, с глас и субтитри, без камера.

Сглобяването е с ffmpeg. Кадрите са: твои истински клипове/снимки от
кабинета (най-добре) или AI кадри от KIE Veo (без AI „пациенти“).
Субтитрите се рисуват с шрифта на марката, буква по буква вярно.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import banneri
from .config import MashinaGreshka

W, H, FPS = 1080, 1920, 30
SNIMKI = {".jpg", ".jpeg", ".png", ".webp"}


def _ffmpeg(*args: str) -> None:
    if not shutil.which("ffmpeg"):
        raise MashinaGreshka("Няма ffmpeg. Инсталирай го (виж START.md → урок 02).")
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise MashinaGreshka(f"ffmpeg: {r.stderr.strip()[-600:]}")


def prodalzhitelnost(pat: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(pat)],
                       capture_output=True, text=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except (KeyError, ValueError):
        raise MashinaGreshka(f"Не мога да прочета продължителността на {pat}") from None


AUDIO = (".mp3", ".m4a", ".wav", ".aac", ".ogg", ".opus", ".mp4", ".mov")


def nameri_glas(papka: Path, kod: str) -> Path | None:
    """Гласът: video/<код>_glas.<всякакъв формат> — запис от телефона (m4a от iPhone) или от KIE (mp3)."""
    for ext in AUDIO:
        pat = papka / "video" / f"{kod}_glas{ext}"
        if pat.exists():
            return pat
    return None


def _segment(vhod: Path, sek: float, izhod: Path, ot: float = 0.0) -> None:
    mashtab = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}"
    if vhod.suffix.lower() in SNIMKI:
        kadri = int(sek * FPS)
        # бавно приближаване, за да не е статично
        vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
              f"zoompan=z='min(zoom+0.0007,1.08)':d={kadri}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1")
        _ffmpeg("-loop", "1", "-i", str(vhod), "-t", f"{sek:.2f}", "-vf", vf,
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(izhod))
    else:
        _ffmpeg("-ss", f"{ot:.2f}", "-i", str(vhod), "-t", f"{sek:.2f}", "-vf", mashtab,
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(izhod))


def avto_subtitri(tekst: str, obshto_sek: float, dumi_na_red: int = 4) -> list[dict]:
    """Разделя текста на парчета до 4 думи и ги разпределя по дължина."""
    dumi = tekst.split()
    parcheta = [" ".join(dumi[i:i + dumi_na_red]) for i in range(0, len(dumi), dumi_na_red)]
    if not parcheta:
        return []
    znaci = [len(p) + 3 for p in parcheta]
    s = sum(znaci)
    t, rez = 0.0, []
    for p, z in zip(parcheta, znaci):
        d = obshto_sek * z / s
        rez.append({"ot": round(t, 2), "do": round(t + d, 2), "tekst": p})
        t += d
    return rez


def _subtitar_png(tekst: str, cfg, izhod: Path) -> Path:
    m = cfg["marka"]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    font = banneri._font(m["shrift_zaglavie"], 72)
    redove = banneri._prenesi([(x, False) for x in tekst.split()], font, W - 200)
    y = int(H * 0.62)
    for red in redove:
        s = " ".join(x for x, _ in red)
        tw = font.getlength(s)
        x = (W - tw) / 2
        d.rounded_rectangle((x - 28, y - 10, x + tw + 28, y + 92), radius=22, fill=m["cvqt_osnoven"] + "E6")
        d.text((x, y), s, font=font, fill="#FFFFFF")
        y += 112
    im.save(izhod)
    return izhod


def _krayna_karta(v: dict, cfg, izhod: Path, snimka: str | None, papka: Path) -> Path:
    b = {"kod": v["kod"] + "-krai", "oformlenie": "snimka", "snimka": snimka or "",
         "zaglavie": v.get("priziv") or cfg["marka"]["hapche_tekst"], "akcent": v.get("priziv_akcent", ""),
         "podzaglavie": cfg["biznes"].get("adres", "")}
    return banneri.napravi(b, "9x16", cfg, papka, izhod)


def sglobi(v: dict, papka: Path, cfg) -> Path:
    """v = видео от matrica.json. Кадрите са пътища спрямо папката на партидата."""
    rabota = papka / "video" / "_rabota" / v["kod"]
    rabota.mkdir(parents=True, exist_ok=True)
    kadri = v.get("kadri") or []
    if not kadri:
        raise MashinaGreshka(f"Видео {v['kod']}: няма кадри. Сложи клипове/снимки в matrica.json → kadri.")

    glas = nameri_glas(papka, v["kod"])
    glas_sek = prodalzhitelnost(glas) if glas else 0.0

    segmenti = []
    for i, k in enumerate(kadri):
        vhod = Path(k["fail"])
        if not vhod.is_absolute():
            vhod = papka / vhod
        if not vhod.exists():
            raise MashinaGreshka(f"Видео {v['kod']}: липсва кадър {vhod}")
        seg = rabota / f"seg{i:02d}.mp4"
        _segment(vhod, float(k.get("sek", 3)), seg, float(k.get("ot", 0)))
        segmenti.append(seg)

    # крайна карта с призива (ако последният кадър не е призив)
    if v.get("krayna_karta", True):
        posledna = kadri[-1]["fail"] if Path(kadri[-1]["fail"]).suffix.lower() in SNIMKI else None
        karta = _krayna_karta(v, cfg, rabota / "krai.png", posledna, papka)
        seg = rabota / "seg_krai.mp4"
        _segment(karta, 2.5, seg)
        segmenti.append(seg)

    spisak = rabota / "spisak.txt"
    spisak.write_text("".join(f"file '{s.resolve()}'\n" for s in segmenti), encoding="utf-8")
    nem = rabota / "nem.mp4"
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(spisak), "-c", "copy", str(nem))
    video_sek = prodalzhitelnost(nem)
    obshto = max(video_sek, glas_sek + 0.4)

    subt = v.get("subtitri") or (avto_subtitri(v.get("glas_tekst", ""), glas_sek or video_sek) if v.get("glas_tekst") else [])
    vhodove = ["-i", str(nem)]
    filtri = []
    posleden = "[0:v]"
    if obshto > video_sek:
        filtri.append(f"{posleden}tpad=stop_mode=clone:stop_duration={obshto - video_sek:.2f}[v0]")
        posleden = "[v0]"
    for i, s in enumerate(subt):
        png = _subtitar_png(s["tekst"], cfg, rabota / f"sub{i:02d}.png")
        vhodove += ["-i", str(png)]
        izh = f"[v{i + 1}]"
        filtri.append(f"{posleden}[{i + 1}:v]overlay=0:0:enable='between(t,{s['ot']},{s['do']})'{izh}")
        posleden = izh
    audio_idx = None
    if glas:
        audio_idx = len(subt) + 1
        vhodove += ["-i", str(glas)]

    izhod = papka / "video" / f"{v['kod']}.mp4"
    args = [*vhodove]
    if filtri:
        args += ["-filter_complex", ";".join(filtri), "-map", posleden]
    else:
        args += ["-map", "0:v"]
    if audio_idx is not None:
        args += ["-map", f"{audio_idx}:a", "-c:a", "aac", "-b:a", "160k"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-t", f"{obshto:.2f}",
             "-movflags", "+faststart", str(izhod)]
    _ffmpeg(*args)
    # корица за Meta
    _ffmpeg("-ss", "0.5", "-i", str(izhod), "-frames:v", "1", str(papka / "video" / f"{v['kod']}_korica.jpg"))
    return izhod
