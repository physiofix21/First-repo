"""Meta Marketing API: победителите, качването на пауза, числата за отчета.

Всичко, което се създава, е със status=PAUSED. Машината НИКОГА не пуска
реклама и не сменя бюджет на пусната реклама. Пускаш ти, от линка.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import partida as P
from .config import MashinaGreshka, chetI_json, pishi_json
from .http import zayavka

REZULTAT_DEISTVIA = {
    "messages": ["onsite_conversion.messaging_conversation_started_7d"],
    "calls": ["click_to_call_native_call_placed", "click_to_call_call_confirm"],
    "leads": ["lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead"],
    "purchases": ["purchase", "offsite_conversion.fb_pixel_purchase", "omni_purchase"],
}
DESTINACII = {
    "MESSENGER": ("MESSENGER", "MESSENGER"),
    "INSTAGRAM_DIRECT": ("INSTAGRAM_DIRECT", "INSTAGRAM_DIRECT"),
    "WHATSAPP": ("WHATSAPP", "WHATSAPP"),
}


class Meta:
    def __init__(self, cfg):
        self.cfg = cfg
        self.token = cfg.env.get("META_ACCESS_TOKEN", "")
        akaunt = cfg.env.get("META_AD_ACCOUNT_ID", "")
        self.akaunt = akaunt if akaunt.startswith("act_") or not akaunt else f"act_{akaunt}"
        self.page = cfg.env.get("META_PAGE_ID", "")
        self.ig = cfg.env.get("META_IG_USER_ID", "")
        self.v = cfg.get("meta", "api_versia", "v23.0")
        self.baza = f"https://graph.facebook.com/{self.v}"

    def proveri_klyuchove(self):
        lipsvat = [k for k, v in {"META_ACCESS_TOKEN": self.token, "META_AD_ACCOUNT_ID": self.akaunt.replace("act_", ""),
                                  "META_PAGE_ID": self.page}.items() if not v]
        if lipsvat:
            raise MashinaGreshka(f"Липсват в .env: {', '.join(lipsvat)}. Виж START.md → урок 02.")

    def get(self, pat: str, **params):
        params["access_token"] = self.token
        return zayavka("GET", f"{self.baza}/{pat}", params=params, timeout=60)

    def post(self, pat: str, forma: dict, failove: dict | None = None):
        forma = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in forma.items()}
        forma["access_token"] = self.token
        if failove:
            return zayavka("POST", f"{self.baza}/{pat}", forma=forma, failove=failove, timeout=600)
        return zayavka("POST", f"{self.baza}/{pat}", forma=forma, timeout=120)

    def vsichki(self, pat: str, **params):
        r = self.get(pat, **params)
        data = list(r.get("data", []))
        while r.get("paging", {}).get("next"):
            r = zayavka("GET", r["paging"]["next"], timeout=60)
            data += r.get("data", [])
        return data

    # ── числа ────────────────────────────────────────────────
    def insights(self, obekt: str, ot: str | None = None, do: str | None = None, nivo: str = "ad",
                 date_preset: str | None = None) -> list[dict]:
        poleta = "ad_id,ad_name,adset_name,campaign_name,spend,impressions,reach,frequency,clicks,ctr,cpm,actions,video_thruplay_watched_actions"
        params = {"level": nivo, "fields": poleta, "limit": 500}
        if date_preset:
            params["date_preset"] = date_preset
        else:
            params["time_range"] = json.dumps({"since": ot, "until": do})
        return self.vsichki(f"{obekt}/insights", **params)


def rezultati(red: dict, cel: str) -> int:
    tipove = REZULTAT_DEISTVIA.get(cel, [])
    nai_mnogo = 0
    for a in red.get("actions") or []:
        if a.get("action_type") in tipove:
            nai_mnogo = max(nai_mnogo, int(float(a.get("value", 0))))
    return nai_mnogo


def normalizirai(red: dict, cel: str) -> dict:
    """Единен ред за отчета — от API или от CSV експорт."""
    spend = float(red.get("spend") or 0)
    rez = rezultati(red, cel) if "actions" in red else int(float(red.get("rezultati") or 0))
    impr = int(float(red.get("impressions") or 0))
    klik = int(float(red.get("clicks") or 0))
    ctr = float(red["ctr"]) if red.get("ctr") not in (None, "") else (100 * klik / impr if impr else 0.0)
    return {
        "ime": red.get("ad_name") or red.get("ime") or "?",
        "adset": red.get("adset_name") or red.get("adset") or "",
        "id": red.get("ad_id") or "",
        "razhod": round(spend, 2),
        "rezultati": rez,
        "cena_rezultat": round(spend / rez, 2) if rez else None,
        "pokazvania": impr,
        "chestota": float(red.get("frequency") or 0),
        "ctr": round(ctr, 2),
    }


# ── победителите (П2: „победителите от акаунта ти първо“) ──
def pobediteli(cfg, dni: int = 90, top: int = 10) -> list[dict]:
    m = Meta(cfg)
    m.proveri_klyuchove()
    do = date.today()
    ot = do - timedelta(days=dni)
    redove = [normalizirai(r, cfg["biznes"]["cel"]) for r in m.insights(m.akaunt, ot.isoformat(), do.isoformat())]
    s_rezultat = [r for r in redove if r["rezultati"] >= 3]
    s_rezultat.sort(key=lambda r: (r["cena_rezultat"], -r["rezultati"]))
    return s_rezultat[:top]


# ── план за качване (Стоп Б) ─────────────────────────────────
def ime_reklama(cfg, m: dict, kod: str, vid: str) -> str:
    tema = P.slug(m["tema"]).replace("-", "")[:14]
    return f"{cfg.prefiks}_{tema}_{kod}_{vid}_v1"


def napravi_plan(p: Path, cfg) -> dict:
    m = P.matrica(p)
    fmt = cfg.get("meta", "format_kachvane", "4x5")
    kopi = m["kopi"]
    rezhim = cfg.get("meta", "tekstove_rezhim", "variacii")
    reklami_obshto = 0
    adseti = []
    for i, a in enumerate(m["adseti"]):
        reklami = []
        for j, b in enumerate(a["banneri"]):
            fail = p / "banneri" / f"{b['kod']}_{fmt}.png"
            reklami.append({"kod": b["kod"], "vid": "banner", "fail": str(fail.relative_to(p)),
                            "ime": ime_reklama(cfg, m, b["kod"], b.get("oformlenie") or "banner"),
                            "tekst_index": (i * 5 + j) % 5})
        for j, v in enumerate(a["video"]):
            fail = p / "video" / f"{v['kod']}.mp4"
            reklami.append({"kod": v["kod"], "vid": "video", "fail": str(fail.relative_to(p)),
                            "korica": str((p / "video" / f"{v['kod']}_korica.jpg").relative_to(p)),
                            "ime": ime_reklama(cfg, m, v["kod"], "video"), "tekst_index": (i + j + 4) % 5})
        reklami_obshto += len(reklami)
        adseti.append({"kod": a["kod"], "ime": a["ime"] or f"{cfg.prefiks} · {a['kod']} · {a['agal']}",
                       "dneven_budjet": m.get("dneven_budjet_na_adset", cfg["test"]["dneven_budjet_na_adset"]),
                       "reklami": reklami})
    budjet_den = sum(a["dneven_budjet"] for a in adseti)
    plan = {
        "kampania": m["kampania"],
        "tip": "ABO",
        "cel": m["cel"],
        "destinacia": cfg.get("meta", "destinacia", "MESSENGER"),
        "status": "PAUSED",
        "tekstove": rezhim,
        "auditoria": {
            "centar": [cfg.get("meta", "shirina"), cfg.get("meta", "dalzhina")],
            "radius_km": cfg.get("meta", "radius_km", 15),
            "vazrast": [cfg.get("meta", "vazrast_min", 25), cfg.get("meta", "vazrast_max", 65)],
        },
        "adseti": adseti,
        "obshto_reklami": reklami_obshto,
        "budjet_na_den": budjet_den,
        "budjet_14_dni": round(budjet_den * cfg["test"].get("dni_na_test", 14), 2),
        "kopi": kopi,
        "kampania_id": m.get("kampania_id"),   # вълна 2 влиза в същата кампания
    }
    # проверка: файловете съществуват
    lipsvat = [r["fail"] for a in adseti for r in a["reklami"] if not (p / r["fail"]).exists()]
    plan["lipsvat_failove"] = lipsvat
    return plan


def pokazhi_plan(plan: dict, cfg) -> str:
    redove = [
        f"Кампания: {plan['kampania']}  ({plan['tip']}, цел: {plan['cel']} → {plan['destinacia']}, всичко НА ПАУЗА)",
        f"Аудитория: {plan['auditoria']['radius_km']} км около {cfg['biznes']['grad']}, {plan['auditoria']['vazrast'][0]}–{plan['auditoria']['vazrast'][1]} г.",
    ]
    for a in plan["adseti"]:
        redove.append(f"  Ad set {a['kod']}: {a['ime']} · {a['dneven_budjet']:.2f} €/ден · {len(a['reklami'])} реклами")
        for r in a["reklami"]:
            redove.append(f"     - {r['ime']}  ({r['fail']})")
    redove.append(f"Общо: {plan['obshto_reklami']} реклами · {plan['budjet_na_den']:.2f} €/ден · до {plan['budjet_14_dni']:.2f} € за 14 дни")
    redove.append(f"Текстове: {'5/5/5 варианта във всяка реклама' if plan['tekstove'] == 'variacii' else 'по един текст на реклама'}")
    if plan["lipsvat_failove"]:
        redove.append(f"✗ Липсват {len(plan['lipsvat_failove'])} файла: " + ", ".join(plan["lipsvat_failove"][:5]))
    return "\n".join(redove)


# ── качване ──────────────────────────────────────────────────
def _targeting(plan: dict) -> dict:
    a = plan["auditoria"]
    return {
        "geo_locations": {"custom_locations": [{
            "latitude": a["centar"][0], "longitude": a["centar"][1],
            "radius": a["radius_km"], "distance_unit": "kilometer"}]},
        "age_min": a["vazrast"][0],
        "age_max": a["vazrast"][1],
        "targeting_automation": {"advantage_audience": 0},
    }


def _cta(cfg) -> dict:
    dest = cfg.get("meta", "destinacia", "MESSENGER")
    tip = cfg.get("meta", "cta", "MESSAGE_PAGE")
    if tip == "MESSAGE_PAGE":
        app = {"MESSENGER": "MESSENGER", "INSTAGRAM_DIRECT": "INSTAGRAM_DIRECT", "WHATSAPP": "WHATSAPP"}[dest]
        return {"type": "MESSAGE_PAGE", "value": {"app_destination": app}}
    return {"type": tip, "value": {"link": cfg["biznes"]["sait"]}}


def kachi(p: Path, cfg, log=print) -> dict:
    """Качва партидата на пауза. Може да се пуска пак: прескача вече създаденото."""
    P.iziskvai(p, "stop_b", "Първо прегледай плана и кажи „да“: `./mashina meta --plan` и после `./mashina meta --da`.")
    m = Meta(cfg)
    m.proveri_klyuchove()
    plan = chetI_json(p / "meta-plan.json")
    if plan.get("lipsvat_failove"):
        raise MashinaGreshka("В плана има липсващи файлове. Направи ги и пусни `./mashina meta --plan` пак.")
    rez_pat = p / "meta-rezultat.json"
    rez = chetI_json(rez_pat, default={"adseti": {}, "reklami": {}, "snimki": {}, "video": {}, "kreativi": {}, "greshki": []})

    def zapazi():
        pishi_json(rez_pat, rez)

    kopi = plan["kopi"]
    dest = plan["destinacia"]

    # 1. кампания
    if not rez.get("kampania_id") and plan.get("kampania_id"):
        rez["kampania_id"] = plan["kampania_id"]          # вълна 2: в съществуващата кампания
    if not rez.get("kampania_id"):
        r = m.post(f"{m.akaunt}/campaigns", {
            "name": plan["kampania"],
            "objective": "OUTCOME_ENGAGEMENT" if plan["cel"] in ("messages", "calls") else "OUTCOME_LEADS",
            "status": "PAUSED",
            "special_ad_categories": [],
            "buying_type": "AUCTION",
            "is_adset_budget_sharing_enabled": "false",
        })
        rez["kampania_id"] = r["id"]
        zapazi()
        log(f"✓ Кампания {r['id']}")

    for a in plan["adseti"]:
        # 2. ad set
        if a["kod"] not in rez["adseti"]:
            r = m.post(f"{m.akaunt}/adsets", {
                "name": a["ime"],
                "campaign_id": rez["kampania_id"],
                "daily_budget": int(round(a["dneven_budjet"] * 100)),
                "billing_event": "IMPRESSIONS",
                "optimization_goal": "CONVERSATIONS",
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                "destination_type": DESTINACII[dest][0],
                "promoted_object": {"page_id": m.page},
                "targeting": _targeting(plan),
                "status": "PAUSED",
            })
            rez["adseti"][a["kod"]] = r["id"]
            zapazi()
            log(f"✓ Ad set {a['kod']} {r['id']}")
        adset_id = rez["adseti"][a["kod"]]

        for rk in a["reklami"]:
            if rk["kod"] in rez["reklami"]:
                continue
            try:
                kreativ_id = _kreativ(m, cfg, p, rk, kopi, plan["tekstove"], rez, zapazi, log)
                r = m.post(f"{m.akaunt}/ads", {
                    "name": rk["ime"], "adset_id": adset_id,
                    "creative": {"creative_id": kreativ_id}, "status": "PAUSED",
                })
                rez["reklami"][rk["kod"]] = r["id"]
                zapazi()
                log(f"  ✓ {rk['ime']}")
            except MashinaGreshka as e:
                rez["greshki"].append({"kod": rk["kod"], "greshka": str(e)})
                zapazi()
                log(f"  ✗ {rk['ime']}: {e}")

    akaunt_nomer = m.akaunt.replace("act_", "")
    rez["link"] = (f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={akaunt_nomer}"
                   f"&selected_campaign_ids={rez['kampania_id']}")
    zapazi()
    return rez


def _kreativ(m: Meta, cfg, p: Path, rk: dict, kopi: dict, rezhim: str, rez: dict, zapazi, log) -> str:
    if rk["kod"] in rez["kreativi"]:
        return rez["kreativi"][rk["kod"]]
    i = rk["tekst_index"]
    osnoven = kopi["osnovni"][i % len(kopi["osnovni"])]
    zaglavie = kopi["zaglaviya"][i % len(kopi["zaglaviya"])]
    opisanie = kopi["opisaniya"][i % len(kopi["opisaniya"])]
    cta = _cta(cfg)
    link_msg = "https://fb.com/messenger_doc/"

    if rk["vid"] == "banner":
        if rk["kod"] not in rez["snimki"]:
            r = m.post(f"{m.akaunt}/adimages", {}, failove={"filename": p / rk["fail"]})
            rez["snimki"][rk["kod"]] = next(iter(r["images"].values()))["hash"]
            zapazi()
        spec = {"page_id": m.page, "link_data": {
            "message": osnoven, "name": zaglavie, "description": opisanie,
            "image_hash": rez["snimki"][rk["kod"]], "link": link_msg, "call_to_action": cta}}
    else:
        if rk["kod"] not in rez["video"]:
            r = m.post(f"{m.akaunt}/advideos", {"name": rk["ime"]}, failove={"source": p / rk["fail"]})
            rez["video"][rk["kod"]] = r["id"]
            zapazi()
        kor_kod = rk["kod"] + "_korica"
        if kor_kod not in rez["snimki"]:
            r = m.post(f"{m.akaunt}/adimages", {}, failove={"filename": p / rk["korica"]})
            rez["snimki"][kor_kod] = next(iter(r["images"].values()))["hash"]
            zapazi()
        spec = {"page_id": m.page, "video_data": {
            "video_id": rez["video"][rk["kod"]], "image_hash": rez["snimki"][kor_kod],
            "message": osnoven, "title": zaglavie, "link_description": opisanie, "call_to_action": cta}}
    if m.ig:
        spec["instagram_user_id"] = m.ig

    forma = {"name": rk["ime"], "object_story_spec": spec}
    if rezhim == "variacii":
        # 5/5/5: Meta сама комбинира текстовете за всеки човек
        forma["asset_feed_spec"] = {
            "bodies": [{"text": t} for t in kopi["osnovni"]],
            "titles": [{"text": t} for t in kopi["zaglaviya"]],
            "descriptions": [{"text": t} for t in kopi["opisaniya"]],
            "optimization_type": "DEGREES_OF_FREEDOM",
        }
    try:
        r = m.post(f"{m.akaunt}/adcreatives", forma)
    except MashinaGreshka as e:
        if rezhim != "variacii":
            raise
        log(f"  ! 5/5/5 не мина за {rk['kod']} ({str(e)[:120]}…) → качвам с един текст")
        forma.pop("asset_feed_spec")
        r = m.post(f"{m.akaunt}/adcreatives", forma)
    rez["kreativi"][rk["kod"]] = r["id"]
    zapazi()
    return r["id"]
