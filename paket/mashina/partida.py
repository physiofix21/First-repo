"""Партидата: папка с дата, матрица, статус и двете „да“ (Стоп А и Стоп Б)."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .config import PARTIDI, MashinaGreshka, chetI_json, dnes, pishi_json

ETAPI = ["brif", "matrica", "stop_a", "banneri", "video", "kopi", "stop_b", "kachena", "pusnata"]
ETAPI_BG = {
    "brif": "П1 Брифът", "matrica": "П2 Матрицата", "stop_a": "Стоп А (сметката преди парите)",
    "banneri": "П3 Банерите", "video": "П3 Видеата", "kopi": "П3 Текстовете 5/5/5",
    "stop_b": "Стоп Б (преди качването)", "kachena": "П4 В Meta на пауза", "pusnata": "П4 Пусната (от теб)",
}

LATIN = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sht", "ъ": "a", "ь": "y", "ю": "yu", "я": "ya",
})


def slug(tekst: str) -> str:
    s = tekst.lower().translate(LATIN)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "partida"


def prazna_matrica(tema: str, cfg, ime: str) -> dict:
    t = cfg["test"]
    kodove = "ABCDEFGH"
    adseti = []
    for i in range(t["adseta"]):
        k = kodove[i]
        adseti.append({
            "kod": k,
            "agal": "",               # оферта | болка | доказателство | механизъм | сравнение
            "ime": "",                # попълва се от skill matrica
            "zashto": "",             # защо този ъгъл (от брифа / победителите)
            "banneri": [
                {"kod": f"{k}{j + 1}", "oformlenie": "", "snimka": "", "prompt_snimka": "",
                 "zaglavie": "", "akcent": "", "podzaglavie": "", "hapche": ""}
                for j in range(t["banera_na_adset"])
            ],
            "video": [
                {"kod": f"{k}V{j + 1}", "huk": "", "tyalo": "", "priziv": "", "glas_tekst": "",
                 "kadri": [], "subtitri": []}
                for j in range(t["video_na_adset"])
            ],
        })
    return {
        "partida": ime,
        "tema": tema,
        "data": dnes(),
        "cel": cfg["biznes"]["cel"],
        "dneven_budjet_na_adset": t["dneven_budjet_na_adset"],
        "kampania": f"{cfg.prefiks} · {tema} · {dnes()}",
        "adseti": adseti,
        "kopi": {"osnovni": [], "zaglaviya": [], "opisaniya": []},
    }


def nova(tema: str, cfg, vulna_ot: str | None = None) -> Path:
    ime = f"{dnes()}_{slug(tema)}"
    p = PARTIDI / ime
    n = 2
    while p.exists():
        p = PARTIDI / f"{ime}-{n}"
        n += 1
    for pod in ("banneri", "video", "snimki", "surovo"):
        (p / pod).mkdir(parents=True, exist_ok=True)
    pishi_json(p / "matrica.json", prazna_matrica(tema, cfg, p.name))
    status = {"partida": p.name, "tema": tema, "sazdadena": datetime.now().isoformat(timespec="seconds"),
              "etapi": {e: None for e in ETAPI}}
    if vulna_ot:
        status["vulna_ot"] = vulna_ot
    pishi_json(p / "status.json", status)
    (p / "brif.md").write_text(BRIF_SHABLON.format(tema=tema), encoding="utf-8")
    return p


def status(p: Path) -> dict:
    return chetI_json(p / "status.json")


def otbeleji(p: Path, etap: str, info=True) -> None:
    if etap not in ETAPI:
        raise MashinaGreshka(f"Непознат етап {etap}")
    s = status(p)
    s["etapi"][etap] = {"koga": datetime.now().isoformat(timespec="seconds"), "info": info} if info is not None else None
    pishi_json(p / "status.json", s)


def gotov(p: Path, etap: str) -> bool:
    return bool(status(p)["etapi"].get(etap))


def iziskvai(p: Path, etap: str, zashto: str) -> None:
    if not gotov(p, etap):
        raise MashinaGreshka(f"Спирам: „{ETAPI_BG[etap]}“ още не е минат. {zashto}")


def matrica(p: Path) -> dict:
    return chetI_json(p / "matrica.json")


def vsichki_banneri(m: dict):
    for a in m["adseti"]:
        for b in a["banneri"]:
            yield a, b


def vsichki_video(m: dict):
    for a in m["adseti"]:
        for v in a["video"]:
            yield a, v


def pokazhi_status(p: Path) -> str:
    s = status(p)
    redove = [f"Партида {s['partida']} — {s['tema']}"]
    for e in ETAPI:
        st = s["etapi"].get(e)
        redove.append(f"  {'✓' if st else '·'} {ETAPI_BG[e]}" + (f"  ({st['koga'][:16]})" if st else ""))
    sledvasht = next((e for e in ETAPI if not s["etapi"].get(e)), None)
    redove.append(f"→ Следва: {ETAPI_BG[sledvasht]}" if sledvasht else "→ Партидата е пусната. Следва отчет в ден 3.")
    return "\n".join(redove)


def spisak() -> str:
    papki = sorted(p for p in PARTIDI.glob("*") if p.is_dir())
    if not papki:
        return "Още няма партиди."
    redove = []
    for p in papki:
        try:
            s = status(p)
            posleden = [e for e in ETAPI if s["etapi"].get(e)]
            redove.append(f"  {p.name:45} {ETAPI_BG[posleden[-1]] if posleden else 'нова'}")
        except MashinaGreshka:
            redove.append(f"  {p.name:45} (няма status.json)")
    return "\n".join(redove)


BRIF_SHABLON = """# Бриф: {tema}

> Попълва се от skill `brif` (П1 · Проучваш). Всичко тук е от истински източници: линк или цитат до всяко твърдение.

## 1. Какво продаваме и на кого
- Услуга:
- Кой идва (ситуация, роля, място — не диагноза):
- Какво иска да получи:

## 2. Гласът на клиента (Google отзиви, съобщения, коментари)
| Цитат | Източник | Какво ни казва |
|---|---|---|

## 3. Възраженията
| Възражение | Как го отговаряме в рекламата |
|---|---|

## 4. Конкурентите (Meta Ad Library) — само за ъгли, никога не ги споменаваме
| Кабинет | Ъгъл | Формат | От колко време върви |
|---|---|---|---|

## 5. Победителите от нашия акаунт (`./mashina pobediteli`)

## 6. Ъглите, които продават (3–5)
| Ъгъл | Хук (до 8 думи) | Доказателство | Тип |
|---|---|---|---|

## 7. Може / не може
| ✓ Може | ✕ Не може |
|---|---|
| Ситуация: „болката в кръста след 8 часа седене“ | „Теб те боли кръстът?“ |
| „План за лечение след преглед“ | „Излекуваме“, „гарантирано“ |
| Терапевт показва упражнение | Преди/след, AI „пациенти“ |
| „5.0 от {{отзиви}} отзива в Google“ | Цени, отстъпки, таймери |
"""
