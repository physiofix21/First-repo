"""П5 · Претегляш: отчетът в ден 3, 7 и 14.

За всяка реклама: СПРИ, ОСТАВИ или УМНОЖИ — с числото до решението.
Машината само предлага. Спираш/пускаш ти (или казваш „да“ и машината спира
рекламата на пауза — никога не пуска и не вдига бюджет).
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from . import partida as P
from .config import OTCHETI, MashinaGreshka, chetI_json, dnes
from .meta import Meta, normalizirai

RANO = "РАНО"
SPRI = "СПРИ"
OSTAVI = "ОСТАВИ"
UMNOZHI = "УМНОЖИ"


def reshi(r: dict, den: int, tavan: float) -> tuple[str, str]:
    """Правилата 3-7-14. r = нормализиран ред; tavan = макс € за резултат."""
    razhod, rez, cpr, ctr = r["razhod"], r["rezultati"], r["cena_rezultat"], r["ctr"]
    cpr_t = f"{cpr:.2f} € на резултат" if cpr else "0 резултата"
    # навсякъде: изгорял бюджет без резултат
    if rez == 0 and razhod >= 2 * tavan:
        return SPRI, f"{razhod:.2f} € и 0 резултата (≥ 2× таван {tavan:.2f} €)"
    if den < 3:
        return RANO, f"ден {den}: не пипай. {razhod:.2f} €, {cpr_t}"
    if den < 7:
        if r["pokazvania"] >= 1500 and ctr < 0.6:
            return SPRI, f"CTR {ctr:.2f}% при {r['pokazvania']} показвания — хукът не спира пръста"
        if cpr and cpr > 2 * tavan and razhod >= 1.5 * tavan:
            return SPRI, f"{cpr_t}, над 2× тавана {tavan:.2f} €"
        return OSTAVI, f"{cpr_t} · CTR {ctr:.2f}% — събира данни до ден 7"
    # ден 7+
    if cpr and cpr > 1.5 * tavan:
        return SPRI, f"{cpr_t}, над 1.5× тавана {tavan:.2f} €"
    if den >= 14 and r["chestota"] >= 3.0 and cpr and cpr > tavan:
        return SPRI, f"умора: честота {r['chestota']:.1f} и {cpr_t}"
    if cpr and rez >= 3 and cpr <= 0.8 * tavan:
        bel = "" if rez >= 10 else " (под 10 резултата — умножи внимателно)"
        return UMNOZHI, f"{cpr_t} ≤ 80% от тавана {tavan:.2f} € · {rez} резултата{bel}"
    if cpr and cpr <= tavan:
        return OSTAVI, f"{cpr_t} — под тавана {tavan:.2f} €"
    return OSTAVI, f"{cpr_t} — между тавана и 1.5×, гледай пак в ден {14 if den < 14 else den + 7}"


# ── данни ────────────────────────────────────────────────────
KOLONI = {
    "ime": ["ad name", "име на рекламата", "реклама"],
    "adset": ["ad set name", "име на рекламния набор", "рекламен набор"],
    "spend": ["amount spent", "изразходвана сума", "похарчена сума"],
    "rezultati": ["results", "резултати"],
    "impressions": ["impressions", "импресии", "показвания"],
    "clicks": ["link clicks", "clicks (all)", "кликвания върху линка", "кликвания (всички)"],
    "ctr": ["ctr (all)", "ctr (link click-through rate)", "ctr (всички)", "ctr"],
    "frequency": ["frequency", "честота"],
}


def ot_csv(pat: Path, cel: str) -> list[dict]:
    """Експорт от Ads Manager (ниво реклама), на английски или български."""
    with pat.open(encoding="utf-8-sig") as f:
        chetec = csv.DictReader(f)
        karta = {}
        for kluch, varianti in KOLONI.items():
            for kol in chetec.fieldnames or []:
                k = kol.lower()
                if any(k.startswith(v) for v in varianti):
                    karta.setdefault(kluch, kol)
        if "ime" not in karta or "spend" not in karta:
            raise MashinaGreshka(f"Не разпознавам колоните в {pat.name}. Нужни са поне „Ad name“ и „Amount spent“.")
        redove = []
        for red in chetec:
            if not red.get(karta["ime"]):
                continue
            def ch(k):
                v = red.get(karta.get(k, ""), "") or "0"
                return v.replace(",", ".").replace("%", "").strip() or "0"
            redove.append(normalizirai({
                "ime": red[karta["ime"]], "adset": red.get(karta.get("adset", ""), ""),
                "spend": ch("spend"), "rezultati": ch("rezultati"), "impressions": ch("impressions"),
                "clicks": ch("clicks"), "ctr": ch("ctr") if "ctr" in karta else None, "frequency": ch("frequency"),
            }, cel))
    return redove


def ot_api(p: Path, cfg) -> list[dict]:
    rez = chetI_json(p / "meta-rezultat.json")
    m = Meta(cfg)
    m.proveri_klyuchove()
    pusk = _den_pusk(p)
    redove = m.insights(rez["kampania_id"], pusk.isoformat(), date.today().isoformat())
    return [normalizirai(r, cfg["biznes"]["cel"]) for r in redove]


def _den_pusk(p: Path) -> date:
    s = P.status(p)
    pusk = s["etapi"].get("pusnata")
    if not pusk:
        raise MashinaGreshka("Не знам кога е пусната партидата. Когато я пуснеш: `./mashina pusnah`.")
    return datetime.fromisoformat(pusk["koga"]).date()


# ── отчетът ──────────────────────────────────────────────────
def napravi(p: Path, cfg, redove: list[dict], den: int | None = None) -> tuple[Path, list[dict]]:
    if den is None:
        den = (date.today() - _den_pusk(p)).days
    tavan = cfg.tavan_rezultat
    for r in redove:
        r["reshenie"], r["zashto"] = reshi(r, den, tavan)
    red_reshenia = {UMNOZHI: 0, OSTAVI: 1, RANO: 2, SPRI: 3}
    redove.sort(key=lambda r: (red_reshenia[r["reshenie"]], r["cena_rezultat"] or 1e9))

    razhod = sum(r["razhod"] for r in redove)
    rez = sum(r["rezultati"] for r in redove)
    sredno = razhod / rez if rez else None
    pobeditel = next((r for r in redove if r["reshenie"] == UMNOZHI), None)

    OTCHETI.mkdir(exist_ok=True)
    izhod = OTCHETI / f"{dnes()}_{p.name}_den{den}.md"
    L = [
        f"# Отчет · ден {den} · {p.name}",
        "",
        f"**Разход:** {razhod:.2f} € · **Резултати ({cfg['biznes']['cel']}):** {rez} · "
        f"**Средно:** {f'{sredno:.2f} €' if sredno else '—'} · **Таван:** {tavan:.2f} € на резултат",
        "",
    ]
    if not cfg.get("ikonomika", "popalneno", False):
        L += ["> ⚠ Таванът е сметнат от приблизителни числа в biznes.toml → [ikonomika]. Попълни истинските.", ""]
    L += ["| Решение | Реклама | Разход | Резултати | € / резултат | CTR | Честота | Защо |",
          "|---|---|---:|---:|---:|---:|---:|---|"]
    for r in redove:
        L.append(f"| **{r['reshenie']}** | {r['ime']} | {r['razhod']:.2f} | {r['rezultati']} | "
                 f"{r['cena_rezultat'] if r['cena_rezultat'] is not None else '—'} | {r['ctr']:.2f}% | {r['chestota']:.1f} | {r['zashto']} |")
    L += ["", "## Какво правиш сега"]
    spri = [r for r in redove if r["reshenie"] == SPRI]
    if spri:
        L.append(f"- Спри {len(spri)}: " + ", ".join(r["ime"] for r in spri) + " (или кажи „да“ и машината ги слага на пауза).")
    if den < 3:
        L.append("- Нищо не пипай до ден 3. Meta още учи.")
    if pobeditel and den >= 7:
        L.append(f"- Умножи победителя **{pobeditel['ime']}**: `./mashina umnozhi {pobeditel['ime']}` → нов ad set „· вълна 2“.")
    elif den >= 14:
        L.append("- Няма ясен победител. Следващата партида: нови ъгли от брифа, старите губещи не се повтарят.")
    L.append(f"- Следващ отчет: ден {7 if den < 7 else 14 if den < 14 else den + 7}.")
    izhod.write_text("\n".join(L) + "\n", encoding="utf-8")

    # дневник на решенията
    dnevnik = OTCHETI / "dnevnik.csv"
    nov = not dnevnik.exists()
    with dnevnik.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if nov:
            w.writerow(["data", "partida", "den", "reklama", "adset", "razhod", "rezultati", "cena_rezultat", "ctr", "chestota", "reshenie", "zashto"])
        for r in redove:
            w.writerow([dnes(), p.name, den, r["ime"], r["adset"], r["razhod"], r["rezultati"],
                        r["cena_rezultat"] if r["cena_rezultat"] is not None else "", r["ctr"], r["chestota"], r["reshenie"], r["zashto"]])
    return izhod, redove


def spri_na_pauza(p: Path, cfg, imena: list[str], log=print) -> None:
    """Слага рекламите на пауза (само пауза, никога пускане)."""
    rez = chetI_json(p / "meta-rezultat.json")
    m = Meta(cfg)
    m.proveri_klyuchove()
    plan = chetI_json(p / "meta-plan.json")
    po_ime = {r["ime"]: r["kod"] for a in plan["adseti"] for r in a["reklami"]}
    for ime in imena:
        kod = po_ime.get(ime)
        ad_id = rez["reklami"].get(kod) if kod else None
        if not ad_id:
            log(f"  ? не намирам {ime}")
            continue
        m.post(ad_id, {"status": "PAUSED"})
        log(f"  ⏸ {ime}")
