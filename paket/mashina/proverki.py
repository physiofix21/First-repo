"""Проверки на текстовете: буква по буква, здравни правила, цени, дължини.

Всяка проверка връща списък от Zabelezhka. „greshka“ спира партидата,
„vnimanie“ се показва, но не спира.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

KIRILICA = re.compile(r"[Ѐ-ӿ]")
LATINICA = re.compile(r"[A-Za-z]")
# латински букви, които изглеждат като кирилски (най-честата AI/копи-пейст грешка)
DVOINICI = set("AaBCcEeHKMOoPpTXxYy")

LIMITI = {
    # (препоръчано, твърд максимум)
    "osnoven":   (125, 600),   # вижда се до ~125 знака без „Още“
    "zaglavie":  (40, 60),
    "opisanie":  (30, 40),
    "banner_zaglavie": (8, 10),  # в думи
}

CENI = re.compile(
    r"(\d+[\s,.]?\d*\s?(€|евро|eur|лв\.?|лева|bgn))|(€\s?\d)|\b(цена|цени|цената|отстъпка|промоция|намаление|безплатн\w*)\b",
    re.IGNORECASE,
)
ZDRAVEN_TI = re.compile(
    r"\b(твоят[аи]?|твоите)\s+(болк\w*|травм\w*|диагноз\w*|херни\w*|дискова\w*)|\bимаш\s+(болк\w*|херни\w*|дискова\w*)",
    re.IGNORECASE,
)


@dataclass
class Zabelezhka:
    nivo: str      # greshka | vnimanie
    kade: str      # напр. „основен текст 3“
    tekst: str

    def __str__(self) -> str:
        znak = "✗" if self.nivo == "greshka" else "!"
        return f"  {znak} {self.kade}: {self.tekst}"


def bukva_po_bukva(tekst: str, kade: str) -> list[Zabelezhka]:
    """Хваща думи със смесени кирилски и латински букви (Р вместо P и т.н.)."""
    zab = []
    for duma in re.findall(r"[\wЀ-ӿ]+", tekst):
        if KIRILICA.search(duma) and LATINICA.search(duma):
            lat = "".join(sorted({c for c in duma if LATINICA.match(c)}))
            zab.append(Zabelezhka("greshka", kade, f"„{duma}“ смесва кирилица и латиница ({lat}). Напиши я наново на кирилица."))
    if "  " in tekst:
        zab.append(Zabelezhka("vnimanie", kade, "двоен интервал"))
    if tekst != tekst.strip():
        zab.append(Zabelezhka("vnimanie", kade, "интервал в началото или края"))
    if re.search(r'"[^"]+"', tekst):
        zab.append(Zabelezhka("vnimanie", kade, 'прави кавички "…" → използвай „…“'))
    if re.search(r"\s[,.!?:;]", tekst):
        zab.append(Zabelezhka("vnimanie", kade, "интервал преди препинателен знак"))
    return zab


def pravila(tekst: str, kade: str, cfg) -> list[Zabelezhka]:
    zab = []
    malki = tekst.lower()
    for duma in cfg.get("pravila", "zabraneni_dumi", []):
        if duma.lower() in malki:
            zab.append(Zabelezhka("greshka", kade, f"забранено: „{duma}“ (здравни правила на Meta / спешност)"))
    for nachalo in cfg.get("pravila", "zabraneni_nachala", []):
        if malki.startswith(nachalo.lower()):
            zab.append(Zabelezhka("greshka", kade, f"скучно начало „{nachalo}…“ — смени хука"))
    if cfg.get("pravila", "zabraneni_ceni", True):
        m = CENI.search(tekst)
        if m:
            zab.append(Zabelezhka("greshka", kade, f"цена/оферта в рекламата: „{m.group(0).strip()}“ — цените се казват в съобщенията"))
    m = ZDRAVEN_TI.search(tekst)
    if m:
        zab.append(Zabelezhka("greshka", kade, f"личен здравен признак „{m.group(0)}“ — говори за ситуацията, не за диагнозата на човека"))
    return zab


def dalzhina(tekst: str, vid: str, kade: str) -> list[Zabelezhka]:
    prep, maks = LIMITI[vid]
    if vid == "banner_zaglavie":
        n = len(tekst.split())
        if n > maks:
            return [Zabelezhka("greshka", kade, f"{n} думи на банера (максимум {maks}, идеално до {prep})")]
        if n > prep:
            return [Zabelezhka("vnimanie", kade, f"{n} думи — над {prep} се чете трудно на телефон")]
        return []
    n = len(tekst)
    if n == 0:
        return [Zabelezhka("greshka", kade, "празно")]
    if n > maks:
        return [Zabelezhka("greshka", kade, f"{n} знака (максимум {maks})")]
    if vid != "osnoven" and n > prep:
        return [Zabelezhka("vnimanie", kade, f"{n} знака — Meta реже след ~{prep}")]
    if vid == "osnoven":
        parvi = tekst.split("\n")[0]
        if len(parvi) > prep:
            return [Zabelezhka("vnimanie", kade, f"първият ред е {len(parvi)} знака — хукът трябва да е в първите {prep}")]
    return []


def proveri_tekst(tekst: str, vid: str, kade: str, cfg) -> list[Zabelezhka]:
    return bukva_po_bukva(tekst, kade) + pravila(tekst, kade, cfg) + dalzhina(tekst, vid, kade)


def proveri_kopi(kopi: dict, cfg) -> list[Zabelezhka]:
    """Проверява 5/5/5: основни текстове, заглавия, описания."""
    zab: list[Zabelezhka] = []
    imena = {"osnovni": ("osnoven", "основен текст"), "zaglaviya": ("zaglavie", "заглавие"), "opisaniya": ("opisanie", "описание")}
    for kluch, (vid, ime) in imena.items():
        spisak = kopi.get(kluch, [])
        if len(spisak) != 5:
            zab.append(Zabelezhka("greshka", ime, f"трябват 5, има {len(spisak)}"))
        vidyani = set()
        for i, t in enumerate(spisak, 1):
            kade = f"{ime} {i}"
            zab += proveri_tekst(t, vid, kade, cfg)
            norm = re.sub(r"\W+", " ", t.lower()).strip()
            if norm in vidyani:
                zab.append(Zabelezhka("greshka", kade, "повтаря друг текст"))
            vidyani.add(norm)
    return zab


def proveri_banner(b: dict, cfg) -> list[Zabelezhka]:
    kade = f"банер {b.get('kod', '?')}"
    zab = proveri_tekst(b.get("zaglavie", ""), "banner_zaglavie", kade, cfg)
    for pole in ("podzaglavie", "hapche", "akcent"):
        if b.get(pole):
            zab += bukva_po_bukva(b[pole], f"{kade} ({pole})") + pravila(b[pole], f"{kade} ({pole})", cfg)
    if b.get("akcent") and b["akcent"].lower() not in b.get("zaglavie", "").lower():
        zab.append(Zabelezhka("greshka", kade, f"акцентът „{b['akcent']}“ го няма в заглавието"))
    return zab


def ima_greshki(zab: list[Zabelezhka]) -> bool:
    return any(z.nivo == "greshka" for z in zab)


def pokazhi(zab: list[Zabelezhka], zaglavie: str) -> str:
    if not zab:
        return f"✓ {zaglavie}: всичко е наред"
    g = sum(z.nivo == "greshka" for z in zab)
    v = len(zab) - g
    redove = [f"{'✗' if g else '!'} {zaglavie}: {g} грешки, {v} внимание"]
    redove += [str(z) for z in zab]
    return "\n".join(redove)
