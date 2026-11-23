"""Стоп А: точната сметка преди парите."""
from __future__ import annotations

from pathlib import Path

from . import partida as P
from .proverki import Zabelezhka, bukva_po_bukva, ima_greshki, pravila, proveri_banner
from .proverki import pokazhi as pokazhi_zabelezhki


def presmetni(p: Path, cfg) -> dict:
    m = P.matrica(p)
    c = cfg.data.get("ceni_generirane", {})
    ai_snimki = sum(1 for _, b in P.vsichki_banneri(m) if not b.get("snimka") and b.get("prompt_snimka"))
    tvoi_snimki = sum(1 for _, b in P.vsichki_banneri(m) if b.get("snimka"))
    ai_sekundi = 0.0
    glasove = 0
    for _, v in P.vsichki_video(m):
        for k in v.get("kadri", []):
            if k.get("ai_prompt") and not k.get("fail"):
                ai_sekundi += float(k.get("sek", 8))
        if v.get("glas_tekst"):
            glasove += 1
    if not cfg.get("kie", "vkluchen", False):
        c = {}
    generirane = (ai_snimki * c.get("snimka_ai", 0) + ai_sekundi * c.get("video_sekunda_ai", 0)
                  + glasove * c.get("glas_tts", 0))
    # резерв 30% за повторения (буква не е наред, кадър не става)
    generirane_rezerv = generirane * 1.3
    adseti = len(m["adseti"])
    budjet_den = adseti * m.get("dneven_budjet_na_adset", cfg["test"]["dneven_budjet_na_adset"])
    dni = cfg["test"].get("dni_na_test", 14)
    return {
        "ai_snimki": ai_snimki, "tvoi_snimki": tvoi_snimki, "ai_sekundi_video": ai_sekundi, "glasove": glasove,
        "generirane": round(generirane, 2), "generirane_s_rezerv": round(generirane_rezerv, 2),
        "reklama_na_den": round(budjet_den, 2), "reklama_obshto": round(budjet_den * dni, 2), "dni": dni,
        "obshto": round(generirane_rezerv + budjet_den * dni, 2),
    }


def proveri_matrica(p: Path, cfg) -> list[Zabelezhka]:
    """Преди парите: всички текстове „на хартия“ трябва да минат проверките."""
    m = P.matrica(p)
    zab: list[Zabelezhka] = []
    for a in m["adseti"]:
        if not a.get("agal"):
            zab.append(Zabelezhka("greshka", f"ad set {a['kod']}", "няма ъгъл"))
    for _, b in P.vsichki_banneri(m):
        if not b.get("zaglavie"):
            zab.append(Zabelezhka("greshka", f"банер {b['kod']}", "няма заглавие"))
            continue
        if not b.get("oformlenie"):
            zab.append(Zabelezhka("greshka", f"банер {b['kod']}", "няма оформление"))
        if not b.get("snimka") and b.get("prompt_snimka") and not cfg.get("kie", "vkluchen", False):
            zab.append(Zabelezhka("greshka", f"банер {b['kod']}", "има само промпт, а KIE.AI е изключен — сложи твоя снимка"))
        if not b.get("snimka") and not b.get("prompt_snimka") and b.get("oformlenie") not in ("sravnenie",):
            zab.append(Zabelezhka("vnimanie", f"банер {b['kod']}", "няма нито снимка, нито промпт — ще е само фон в цвета на марката"))
        zab += proveri_banner(b, cfg)
    for _, v in P.vsichki_video(m):
        if not v.get("huk"):
            zab.append(Zabelezhka("greshka", f"видео {v['kod']}", "няма хук"))
        if not v.get("kadri"):
            zab.append(Zabelezhka("greshka", f"видео {v['kod']}", "няма кадри (сцени)"))
        for pole in ("huk", "glas_tekst", "priziv"):
            if v.get(pole):
                zab += bukva_po_bukva(v[pole], f"видео {v['kod']} ({pole})") + pravila(v[pole], f"видео {v['kod']} ({pole})", cfg)
    return zab


def pokazhi(s: dict, p: Path, cfg) -> str:
    zab = proveri_matrica(p, cfg)
    redove = [
        "СТОП А · сметката преди парите",
        f"  AI снимки: {s['ai_snimki']} (твои снимки: {s['tvoi_snimki']})",
        f"  AI видео: {s['ai_sekundi_video']:.0f} сек · озвучавания: {s['glasove']}"
        + ("" if cfg.get("kie", "vkluchen", False) else "  (KIE.AI е изключен: гласът е твой запис → 0 €)"),
        f"  Генериране: ~{s['generirane']:.2f} € (с 30% резерв за повторения: {s['generirane_s_rezerv']:.2f} €)",
        f"  Реклама: {s['reklama_na_den']:.2f} €/ден × {s['dni']} дни = {s['reklama_obshto']:.2f} €",
        f"  ОБЩО за партидата: ~{s['obshto']:.2f} €",
        "",
        pokazhi_zabelezhki(zab, "Проверка на матрицата"),
    ]
    if ima_greshki(zab):
        redove.append("\n✗ Има грешки „на хартия“. Оправи ги, преди да кажеш „да“.")
    else:
        redove.append("\n→ Ако си съгласен: `./mashina smetka --da`")
    return "\n".join(redove)

