"""Зареждане на biznes.toml, .env и пътищата на машината."""
from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

KOREN = Path(__file__).resolve().parents[2]          # корен на папката ai-reklami
FONTOVE = Path(__file__).resolve().parents[1] / "assets" / "fonts"
PARTIDI = KOREN / "partidi"
OTCHETI = KOREN / "07-otcheti"


class MashinaGreshka(Exception):
    """Грешка, която се показва на човека без traceback."""


def zaredi_env(pat: Path | None = None) -> dict[str, str]:
    """Чете .env (KEY=VALUE). Не печата стойностите никъде."""
    pat = pat or KOREN / ".env"
    rezultat: dict[str, str] = {}
    if pat.exists():
        for red in pat.read_text(encoding="utf-8").splitlines():
            red = red.strip()
            if not red or red.startswith("#") or "=" not in red:
                continue
            k, v = red.split("=", 1)
            rezultat[k.strip()] = v.strip().strip('"').strip("'")
    # променливите от средата са с предимство
    for k in list(rezultat) + ["KIE_API_KEY", "META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID", "META_PAGE_ID", "META_IG_USER_ID"]:
        if os.environ.get(k):
            rezultat[k] = os.environ[k]
    return rezultat


@dataclass
class Config:
    data: dict
    env: dict = field(default_factory=dict)

    def __getitem__(self, k):
        return self.data[k]

    def get(self, sekcia: str, kluch: str, default=None):
        return self.data.get(sekcia, {}).get(kluch, default)

    # ── икономика ──
    @property
    def tavan_nov_pacient(self) -> float:
        ik = self.data["ikonomika"]
        return round(ik["prihod_nov_pacient_60d"] * ik["dyal_za_reklama"], 2)

    @property
    def tavan_rezultat(self) -> float:
        """Максимум € за един резултат (съобщение), за да не губим пари."""
        ik = self.data["ikonomika"]
        return round(self.tavan_nov_pacient * ik["saobshtenie_kam_chas"] * ik["chas_kam_doshal"], 2)

    @property
    def prefiks(self) -> str:
        return self.data["biznes"].get("kratko", "AD")


def zaredi(pat: Path | None = None) -> Config:
    pat = pat or KOREN / "biznes.toml"
    if not pat.exists():
        raise MashinaGreshka(f"Липсва {pat.name}. Копирай примера и го попълни.")
    with pat.open("rb") as f:
        data = tomllib.load(f)
    return Config(data=data, env=zaredi_env())


# ── партиди ──────────────────────────────────────────────────

def papka_partida(ime: str) -> Path:
    p = PARTIDI / ime
    if not p.exists():
        # позволи и само „тема“ → последната партида с тази тема
        kandidati = sorted(PARTIDI.glob(f"*{ime}*"))
        kandidati = [k for k in kandidati if k.is_dir()]
        if not kandidati:
            raise MashinaGreshka(f"Няма партида „{ime}“ в partidi/. Виж `./mashina partida --spisak`.")
        p = kandidati[-1]
    return p


def posledna_partida() -> Path:
    vsichki = sorted(p for p in PARTIDI.glob("*") if p.is_dir())
    if not vsichki:
        raise MashinaGreshka("Още няма партиди. Започни с `./mashina partida нова <тема>`.")
    return vsichki[-1]


def chetI_json(pat: Path, default=None):
    if not pat.exists():
        if default is not None:
            return default
        raise MashinaGreshka(f"Липсва {pat}")
    return json.loads(pat.read_text(encoding="utf-8"))


def pishi_json(pat: Path, data) -> None:
    pat.parent.mkdir(parents=True, exist_ok=True)
    pat.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dnes() -> str:
    return date.today().isoformat()
