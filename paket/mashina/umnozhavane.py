"""Умножаване на победителя: нов ad set „· вълна 2“ с 4 банера и 1 видео на същия ъгъл.

Правило: всеки нов вариант сменя САМО ЕДНА ос спрямо победителя,
за да знаеш какво е спечелило следващия път.
"""
from __future__ import annotations

import copy
from pathlib import Path

from . import partida as P
from .config import PARTIDI, MashinaGreshka, chetI_json, pishi_json

OSI = [
    ("snimka", "същият текст, НОВА снимка/кадър"),
    ("huk", "същата снимка, НОВ хук (заглавие)"),
    ("oformlenie", "същият текст и снимка, ДРУГО оформление"),
    ("podzaglavie", "същото, ново доказателство/подзаглавие"),
]


def nameri(ime_ili_kod: str) -> tuple[Path, dict, dict, str]:
    """Връща (партида, ad set, елемент, вид) за реклама по име от Meta или по код (A2, BV1)."""
    for p in sorted(PARTIDI.glob("*"), reverse=True):
        plan_pat = p / "meta-plan.json"
        if not (p / "matrica.json").exists():
            continue
        m = P.matrica(p)
        kod = ime_ili_kod
        if plan_pat.exists():
            plan = chetI_json(plan_pat)
            for a in plan["adseti"]:
                for r in a["reklami"]:
                    if r["ime"] == ime_ili_kod:
                        kod = r["kod"]
        for a in m["adseti"]:
            for b in a["banneri"]:
                if b["kod"] == kod:
                    return p, a, b, "banner"
            for v in a["video"]:
                if v["kod"] == kod:
                    return p, a, v, "video"
    raise MashinaGreshka(f"Не намирам реклама „{ime_ili_kod}“ в партидите.")


def umnozhi(ime_ili_kod: str, cfg) -> Path:
    p_star, a_star, pobeditel, vid = nameri(ime_ili_kod)
    m_star = P.matrica(p_star)
    nova = P.nova(f"{m_star['tema']} вълна 2", cfg, vulna_ot=p_star.name)
    m = P.matrica(nova)

    adset = {
        "kod": "W",
        "agal": a_star["agal"],
        "ime": f"{a_star['ime'] or a_star['agal']} · вълна 2",
        "zashto": f"Умножен победител {pobeditel['kod']} от {p_star.name}",
        "pobeditel": pobeditel,
        "banneri": [],
        "video": [],
    }
    obrazec = pobeditel if vid == "banner" else (a_star["banneri"][0] if a_star["banneri"] else {})
    for i, (os_, opisanie) in enumerate(OSI, 1):
        b = copy.deepcopy(obrazec)
        b["kod"] = f"W{i}"
        b["smeni"] = os_
        b["belezhka"] = opisanie
        if os_ == "snimka":
            b["snimka"] = ""
        elif os_ == "huk":
            b["zaglavie"], b["akcent"] = "", ""
        elif os_ == "oformlenie":
            b["oformlenie"] = ""
        elif os_ == "podzaglavie":
            b["podzaglavie"] = ""
        adset["banneri"].append(b)
    v_obrazec = pobeditel if vid == "video" else (a_star["video"][0] if a_star["video"] else {"huk": ""})
    v = copy.deepcopy(v_obrazec)
    v.update({"kod": "WV1", "smeni": "huk", "belezhka": "същото тяло и призив, НОВ хук (първите 2–3 сек)", "huk": ""})
    adset["video"].append(v)

    m["adseti"] = [adset]
    m["kopi"] = copy.deepcopy(m_star["kopi"])
    m["kampania"] = m_star["kampania"]
    rez_pat = p_star / "meta-rezultat.json"
    if rez_pat.exists():
        m["kampania_id"] = chetI_json(rez_pat).get("kampania_id")
    pishi_json(nova / "matrica.json", m)
    # брифът и матрицата идват от победителя
    P.otbeleji(nova, "brif", {"ot": p_star.name})
    P.otbeleji(nova, "matrica", {"ot": pobeditel["kod"]})
    return nova
