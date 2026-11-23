"""`./mashina doktor` — проверява ключовете, кредитите, страницата и настройките."""
from __future__ import annotations

import shutil
import sys

from .config import FONTOVE, KOREN, MashinaGreshka


def proveri(cfg, mrezha: bool = True) -> tuple[list[str], int]:
    redove: list[str] = []
    problemi = 0

    def ok(t):
        redove.append(f"  ✓ {t}")

    def lose(t):
        nonlocal problemi
        problemi += 1
        redove.append(f"  ✗ {t}")

    def vnimanie(t):
        redove.append(f"  ! {t}")

    redove.append("Инструменти")
    ok(f"Python {sys.version.split()[0]}") if sys.version_info >= (3, 11) else lose("Трябва Python 3.11+")
    try:
        import PIL
        ok(f"Pillow {PIL.__version__}")
    except ImportError:
        lose("Няма Pillow: pip install pillow")
    ok("ffmpeg") if shutil.which("ffmpeg") else lose("Няма ffmpeg (трябва за видеата)")
    for f in ("Montserrat-Black.ttf", "Manrope-Bold.ttf"):
        ok(f"шрифт {f}") if (FONTOVE / f).exists() else lose(f"липсва шрифт {f}")

    redove.append("Бизнесът (biznes.toml)")
    ik = cfg["ikonomika"]
    if ik.get("popalneno"):
        ok(f"икономиката е попълнена: таван {cfg.tavan_nov_pacient:.2f} € на нов пациент → {cfg.tavan_rezultat:.2f} € на съобщение")
    else:
        vnimanie(f"икономиката е приблизителна (таван {cfg.tavan_rezultat:.2f} € на съобщение). Попълни [ikonomika] и сложи popalneno = true")
    t = cfg["test"]
    aktivni = t["banera_na_adset"] + t["video_na_adset"]
    na_reklama = t["dneven_budjet_na_adset"] / aktivni
    if na_reklama < 1.0:
        vnimanie(f"{t['dneven_budjet_na_adset']:.2f} €/ден за {aktivni} реклами в ad set = {na_reklama:.2f} € на реклама. "
                 "Meta ще даде парите на 1–2 от тях — нормално е, но съди по ad set, не по всяка реклама.")
    else:
        ok(f"бюджет {t['dneven_budjet_na_adset']:.2f} €/ден на ad set")
    if cfg.get("meta", "shirina") == 42.1450:
        vnimanie("координатите на кабинета са примерни — сложи точните в [meta] shirina/dalzhina")

    redove.append("Ключове (.env)")
    env = cfg.env
    if not (KOREN / ".env").exists():
        lose("няма .env — копирай .env.example като .env")
    for k in ("KIE_API_KEY", "META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID", "META_PAGE_ID"):
        ok(f"{k} е попълнен") if env.get(k) and env.get(k) != "act_" else lose(f"{k} липсва")

    if mrezha:
        redove.append("Връзки")
        if env.get("KIE_API_KEY"):
            try:
                from .kie import Kie
                kr = Kie(cfg).krediti()
                (ok if kr >= 50 else vnimanie)(f"KIE.AI: {kr:.0f} кредита")
            except MashinaGreshka as e:
                lose(f"KIE.AI: {e}")
        if env.get("META_ACCESS_TOKEN"):
            try:
                from .meta import Meta
                m = Meta(cfg)
                me = m.get("me", fields="id,name")
                ok(f"Meta токен: {me.get('name', me.get('id'))}")
                if m.akaunt:
                    a = m.get(m.akaunt, fields="name,account_status,currency,amount_spent")
                    st = {1: "активен", 2: "спрян", 3: "неплатен", 7: "в преглед", 9: "гратисен период"}.get(a.get("account_status"), a.get("account_status"))
                    (ok if a.get("account_status") == 1 else lose)(f"рекламен акаунт „{a.get('name')}“: {st}, валута {a.get('currency')}")
                if m.page:
                    pg = m.get(m.page, fields="name")
                    ok(f"страница „{pg.get('name')}“")
            except MashinaGreshka as e:
                lose(f"Meta: {e}")
    redove.append("")
    redove.append("Всичко е наред." if problemi == 0 else f"{problemi} неща за оправяне (виж ✗ горе).")
    return redove, problemi
