"""Командите на машината. Пуска ги AI-ят в папката (Claude Code / Codex), не ти.

  ./mashina doktor                       проверява ключове, кредити, страница
  ./mashina ikonomika                    таванът: колко най-много плащаш за съобщение
  ./mashina partida нова <тема>          нова папка partidi/<дата>_<тема>
  ./mashina partida --spisak             всички партиди
  ./mashina status [партида]             докъде е партидата
  ./mashina pobediteli [--csv файл]      най-добрите реклами от акаунта (90 дни)
  ./mashina proveri "текст"              бърза проверка на текст
  ./mashina smetka [партида] [--da]      СТОП А: сметката и твоето „да“
  ./mashina kie krediti|snimki|glas|kadri [партида]   генериране в KIE.AI (след Стоп А)
  ./mashina banneri [партида]            12 банера × 3 формата + проверка + преглед
  ./mashina video [партида] [код]        сглобява видеата 9:16
  ./mashina kopi [партида]               проверява текстовете 5/5/5
  ./mashina meta [партида] --plan|--da|--kachi   СТОП Б и качване на пауза
  ./mashina pusnah [партида]             записва деня на пускане (ден 0)
  ./mashina otchet [партида] [--csv файл] [--den N] [--spri-da]
  ./mashina umnozhi <реклама>            победителят → нов ad set „· вълна 2“
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import partida as P
from .config import MashinaGreshka, chetI_json, papka_partida, pishi_json, posledna_partida, zaredi


def _p(ime: str | None) -> Path:
    return papka_partida(ime) if ime else posledna_partida()


def cmd_doktor(a, cfg):
    from .doktor import proveri
    redove, problemi = proveri(cfg, mrezha=not a.bez_mrezha)
    print("\n".join(redove))
    return 1 if problemi else 0


def cmd_ikonomika(a, cfg):
    ik = cfg["ikonomika"]
    print(f"Приход от нов пациент (60 дни): {ik['prihod_nov_pacient_60d']:.2f} €")
    print(f"× дял за реклама {ik['dyal_za_reklama']:.0%} = ТАВАН {cfg.tavan_nov_pacient:.2f} € на нов пациент")
    print(f"× съобщение→час {ik['saobshtenie_kam_chas']:.0%} × час→дошъл {ik['chas_kam_doshal']:.0%}")
    print(f"= ТАВАН {cfg.tavan_rezultat:.2f} € на съобщение")
    if not ik.get("popalneno"):
        print("! Числата са приблизителни. Попълни ги в biznes.toml → [ikonomika].")


def cmd_partida(a, cfg):
    if a.spisak or not a.deistvie:
        print(P.spisak())
        return
    if a.deistvie == "нова" or a.deistvie == "nova":
        if not a.tema:
            raise MashinaGreshka("Напиши темата: ./mashina partida нова „болка в кръста“")
        p = P.nova(" ".join(a.tema), cfg)
        print(f"✓ Нова партида: partidi/{p.name}")
        print("  → П1: попълни brif.md (skill brif), после matrica.json (skill matrica).")
        return
    raise MashinaGreshka(f"Непознато: partida {a.deistvie}")


def cmd_status(a, cfg):
    print(P.pokazhi_status(_p(a.partida)))


def cmd_pobediteli(a, cfg):
    from .meta import pobediteli
    if a.csv:
        from .otchet import ot_csv
        redove = [r for r in ot_csv(Path(a.csv), cfg["biznes"]["cel"]) if r["rezultati"] >= 3]
        redove.sort(key=lambda r: r["cena_rezultat"])
        redove = redove[:10]
    else:
        redove = pobediteli(cfg, dni=a.dni)
    if not redove:
        print("Няма реклами с поне 3 резултата. Партидата тръгва от брифа.")
        return
    print(f"Победителите (таван {cfg.tavan_rezultat:.2f} € на резултат):")
    for r in redove:
        znak = "★" if r["cena_rezultat"] <= cfg.tavan_rezultat else " "
        print(f" {znak} {r['cena_rezultat']:6.2f} €  {r['rezultati']:3d} рез.  CTR {r['ctr']:.2f}%  {r['ime']}")


def cmd_proveri(a, cfg):
    from .proverki import pokazhi, proveri_tekst
    tekst = " ".join(a.tekst)
    print(pokazhi(proveri_tekst(tekst, a.vid, "текст", cfg), "Проверка"))


def cmd_smetka(a, cfg):
    from .proverki import ima_greshki
    from .smetka import pokazhi, presmetni, proveri_matrica
    p = _p(a.partida)
    s = presmetni(p, cfg)
    print(pokazhi(s, p, cfg))
    if a.da:
        if ima_greshki(proveri_matrica(p, cfg)):
            raise MashinaGreshka("Не записвам „да“: има грешки в матрицата.")
        if not P.gotov(p, "brif"):
            P.otbeleji(p, "brif", True)
        P.otbeleji(p, "matrica", True)
        P.otbeleji(p, "stop_a", s)
        print(f"\n✓ Стоп А: „да“ за ~{s['obshto']:.2f} €. Може да се генерира.")


def cmd_kie(a, cfg):
    from .kie import Kie
    if not cfg.get("kie", "vkluchen", False):
        raise MashinaGreshka("KIE.AI е изключен (безплатен режим). Гласът: запиши го с телефона → video/<код>_glas.m4a. "
                             "За да го включиш: biznes.toml → [kie] vkluchen = true.")
    k = Kie(cfg)
    if a.deistvie == "krediti":
        print(f"KIE.AI: {k.krediti():.0f} кредита")
        return
    p = _p(a.partida)
    P.iziskvai(p, "stop_a", "Генерирането харчи кредити: първо `./mashina smetka` и твоето „да“.")
    m = P.matrica(p)
    rezhim = cfg.get("kie", "tekst_v_banera", "nadpis")
    if a.deistvie == "snimki":
        for _, b in P.vsichki_banneri(m):
            if b.get("snimka") or not b.get("prompt_snimka"):
                continue
            if a.kod and b["kod"] not in a.kod:
                continue
            if rezhim == "ai":
                prompt = (f"{b['prompt_snimka']}\n\nText on the image, in Bulgarian Cyrillic, EXACTLY letter by letter, "
                          f"no other text: headline „{b['zaglavie']}“" + (f"; small text „{b['podzaglavie']}“" if b.get('podzaglavie') else "")
                          + f"; rounded button „{b.get('hapche') or cfg['marka']['hapche_tekst']}“.")
                izhod = p / "banneri" / f"{b['kod']}_4x5.png"
                k.snimka(prompt, izhod, "4:5")
                b["ai_tekst"] = True
                print(f"  ✓ {b['kod']} (AI с текст) → провери буква по буква: {izhod.relative_to(p)}")
            else:
                izhod = p / "snimki" / f"{b['kod']}.png"
                k.snimka(b["prompt_snimka"] + "\n\nNo text, no letters, no logos on the image.", izhod, "4:5")
                b["snimka"] = str(izhod.relative_to(p))
                print(f"  ✓ {b['kod']} → {b['snimka']}")
            pishi_json(p / "matrica.json", m)
    elif a.deistvie == "glas":
        for _, v in P.vsichki_video(m):
            if a.kod and v["kod"] not in a.kod:
                continue
            if v.get("glas_tekst"):
                izhod = p / "video" / f"{v['kod']}_glas.mp3"
                k.glas(v["glas_tekst"], izhod)
                print(f"  ✓ глас {v['kod']} → {izhod.relative_to(p)}")
    elif a.deistvie == "kadri":
        for _, v in P.vsichki_video(m):
            if a.kod and v["kod"] not in a.kod:
                continue
            for i, kd in enumerate(v.get("kadri", [])):
                if kd.get("fail") or not kd.get("ai_prompt"):
                    continue
                izhod = p / "surovo" / f"{v['kod']}_kadar{i + 1}.mp4"
                k.video(kd["ai_prompt"], izhod, "9:16")
                kd["fail"] = str(izhod.relative_to(p))
                pishi_json(p / "matrica.json", m)
                print(f"  ✓ кадър {v['kod']}/{i + 1} → {kd['fail']}")
    else:
        raise MashinaGreshka("kie: krediti | snimki | glas | kadri")


def cmd_banneri(a, cfg):
    from PIL import Image

    from . import banneri as B
    from .proverki import ima_greshki, pokazhi, proveri_banner
    p = _p(a.partida)
    m = P.matrica(p)
    formati = a.formati.split(",")
    vsichki_zab = []
    gotovi = []
    for _, b in P.vsichki_banneri(m):
        if a.kod and b["kod"] not in a.kod:
            continue
        zab = proveri_banner(b, cfg)
        vsichki_zab += zab
        if ima_greshki(zab):
            continue
        if b.get("ai_tekst"):
            gotovi.append(p / "banneri" / f"{b['kod']}_4x5.png")
            continue
        for f in formati:
            izhod = B.napravi(b, f, cfg, p, p / "banneri" / f"{b['kod']}_{f}.png")
            if f == "4x5":
                gotovi.append(izhod)
    print(pokazhi(vsichki_zab, "Банери буква по буква"))
    if gotovi:
        # лист за преглед: AI-ят го гледа преди Стоп Б
        mini = [Image.open(g).resize((360, 450)) for g in gotovi if g.exists()]
        kol = 4
        red = (len(mini) + kol - 1) // kol
        list_ = Image.new("RGB", (kol * 370 + 10, red * 460 + 10), "#DDDDDD")
        for i, im in enumerate(mini):
            list_.paste(im, (10 + (i % kol) * 370, 10 + (i // kol) * 460))
        list_.save(p / "banneri" / "pregled.png")
        print(f"✓ {len(gotovi)} банера · преглед: partidi/{p.name}/banneri/pregled.png")
    vse = sum(1 for _ in P.vsichki_banneri(m))
    if not ima_greshki(vsichki_zab) and len(gotovi) == vse:
        P.otbeleji(p, "banneri", {"broi": vse, "formati": formati})


def cmd_video(a, cfg):
    from . import animacia
    from .video import sglobi
    p = _p(a.partida)
    m = P.matrica(p)
    n = 0
    if a.otlozheni:
        spisak = [(x, v) for x in m["adseti"] for v in x.get("video_otlozheno", [])]
    else:
        spisak = list(P.vsichki_video(m))
    for _, v in spisak:
        if a.kod and v["kod"] not in a.kod:
            continue
        # със „sceni“ → анимирано видео; иначе → снимки с приближаване
        izhod = animacia.sglobi(v, p, cfg) if v.get("sceni") else sglobi(v, p, cfg)
        n += 1
        print(f"  ✓ {v['kod']} → {izhod.relative_to(p)}")
    if not a.otlozheni:
        vse = sum(1 for _ in P.vsichki_video(m))
        if all((p / "video" / f"{v['kod']}.mp4").exists() for _, v in P.vsichki_video(m)):
            P.otbeleji(p, "video", {"broi": vse})
    print(f"✓ {n} видеа")


def cmd_kopi(a, cfg):
    from .proverki import ima_greshki, pokazhi, proveri_kopi
    p = _p(a.partida)
    m = P.matrica(p)
    zab = proveri_kopi(m["kopi"], cfg)
    print(pokazhi(zab, "Текстове 5/5/5"))
    if not ima_greshki(zab):
        P.otbeleji(p, "kopi", True)
        return 0
    return 1


def cmd_meta(a, cfg):
    from .meta import kachi, napravi_plan, pokazhi_plan
    p = _p(a.partida)
    if a.plan or not (a.da or a.kachi):
        ima_video = any(True for _ in P.vsichki_video(P.matrica(p)))
        for etap in ("banneri", "video", "kopi") if ima_video else ("banneri", "kopi"):
            P.iziskvai(p, etap, "Планът се прави, когато банерите, видеата и текстовете са готови и проверени.")
        plan = napravi_plan(p, cfg)
        pishi_json(p / "meta-plan.json", plan)
        print("СТОП Б · планът за Meta")
        print(pokazhi_plan(plan, cfg))
        if not plan["lipsvat_failove"]:
            print("\n→ Ако си съгласен: `./mashina meta --da` (качва всичко НА ПАУЗА)")
        return
    if a.da:
        plan = chetI_json(p / "meta-plan.json")
        if plan.get("lipsvat_failove"):
            raise MashinaGreshka("Планът има липсващи файлове.")
        P.otbeleji(p, "stop_b", {"reklami": plan["obshto_reklami"], "budjet_na_den": plan["budjet_na_den"]})
        print("✓ Стоп Б: „да“. Качвам на пауза…")
    rez = kachi(p, cfg)
    if not rez.get("greshki"):
        P.otbeleji(p, "kachena", {"kampania_id": rez["kampania_id"]})
    print(f"\n✓ В Ads Manager, на пауза: {rez['link']}")
    print("  Пускаш ти (по възможност в понеделник). После: `./mashina pusnah`.")
    if rez.get("greshki"):
        print(f"! {len(rez['greshki'])} реклами не минаха — виж meta-rezultat.json и пусни `./mashina meta --kachi` пак.")


def cmd_pusnah(a, cfg):
    p = _p(a.partida)
    P.otbeleji(p, "pusnata", True)
    print("✓ Ден 0 записан. Отчетите: ден 3, ден 7, ден 14 → `./mashina otchet`.")


def cmd_otchet(a, cfg):
    from .otchet import SPRI, napravi, ot_api, ot_csv, spri_na_pauza
    p = _p(a.partida)
    redove = ot_csv(Path(a.csv), cfg["biznes"]["cel"]) if a.csv else ot_api(p, cfg)
    if not redove:
        print("Няма данни още.")
        return
    izhod, redove = napravi(p, cfg, redove, a.den)
    print(izhod.read_text(encoding="utf-8"))
    print(f"→ Записан: {izhod.relative_to(izhod.parents[1])} и 07-otcheti/dnevnik.csv")
    if a.spri_da:
        spri = [r["ime"] for r in redove if r["reshenie"] == SPRI]
        spri_na_pauza(p, cfg, spri)


def cmd_umnozhi(a, cfg):
    from .umnozhavane import umnozhi
    nova = umnozhi(" ".join(a.reklama), cfg)
    print(f"✓ Вълна 2: partidi/{nova.name}")
    print("  4 банера (всеки сменя ЕДНА ос) + 1 видео с нов хук. Попълни празните полета → smetka → banneri → …")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mashina", description="Машината 5П: банери, видеа, текстове, Meta на пауза, отчет 3-7-14.")
    sub = ap.add_subparsers(dest="komanda")

    s = sub.add_parser("doktor"); s.add_argument("--bez-mrezha", action="store_true"); s.set_defaults(f=cmd_doktor)
    s = sub.add_parser("ikonomika"); s.set_defaults(f=cmd_ikonomika)
    s = sub.add_parser("partida"); s.add_argument("deistvie", nargs="?"); s.add_argument("tema", nargs="*")
    s.add_argument("--spisak", action="store_true"); s.set_defaults(f=cmd_partida)
    s = sub.add_parser("status"); s.add_argument("partida", nargs="?"); s.set_defaults(f=cmd_status)
    s = sub.add_parser("pobediteli"); s.add_argument("--dni", type=int, default=90); s.add_argument("--csv")
    s.set_defaults(f=cmd_pobediteli)
    s = sub.add_parser("proveri"); s.add_argument("tekst", nargs="+")
    s.add_argument("--vid", default="osnoven", choices=["osnoven", "zaglavie", "opisanie", "banner_zaglavie"]); s.set_defaults(f=cmd_proveri)
    s = sub.add_parser("smetka"); s.add_argument("partida", nargs="?"); s.add_argument("--da", action="store_true"); s.set_defaults(f=cmd_smetka)
    s = sub.add_parser("kie"); s.add_argument("deistvie"); s.add_argument("partida", nargs="?")
    s.add_argument("--kod", nargs="*"); s.set_defaults(f=cmd_kie)
    s = sub.add_parser("banneri"); s.add_argument("partida", nargs="?"); s.add_argument("--formati", default="1x1,4x5,9x16")
    s.add_argument("--kod", nargs="*"); s.set_defaults(f=cmd_banneri)
    s = sub.add_parser("video"); s.add_argument("partida", nargs="?"); s.add_argument("--kod", nargs="*")
    s.add_argument("--otlozheni", action="store_true", help="видеата, отложени за вълна 2"); s.set_defaults(f=cmd_video)
    s = sub.add_parser("kopi"); s.add_argument("partida", nargs="?"); s.set_defaults(f=cmd_kopi)
    s = sub.add_parser("meta"); s.add_argument("partida", nargs="?")
    s.add_argument("--plan", action="store_true"); s.add_argument("--da", action="store_true"); s.add_argument("--kachi", action="store_true")
    s.set_defaults(f=cmd_meta)
    s = sub.add_parser("pusnah"); s.add_argument("partida", nargs="?"); s.set_defaults(f=cmd_pusnah)
    s = sub.add_parser("otchet"); s.add_argument("partida", nargs="?"); s.add_argument("--csv"); s.add_argument("--den", type=int)
    s.add_argument("--spri-da", action="store_true"); s.set_defaults(f=cmd_otchet)
    s = sub.add_parser("umnozhi"); s.add_argument("reklama", nargs="+"); s.set_defaults(f=cmd_umnozhi)

    a = ap.parse_args(argv)
    if not a.komanda:
        print(__doc__)
        return 0
    try:
        cfg = zaredi()
        return a.f(a, cfg) or 0
    except MashinaGreshka as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
