"""Тестове на машината: python3 -m unittest discover -s tests"""
import csv
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN / "paket"))

from mashina import banneri, config, otchet, partida, proverki, smetka  # noqa: E402
from mashina import meta as M  # noqa: E402

CFG = config.zaredi()


class Proverki(unittest.TestCase):
    def test_smesena_kirilica_latinica(self):
        # „Pазбери“ с латинско P
        zab = proverki.bukva_po_bukva("Pазбери защо", "т")
        self.assertTrue(proverki.ima_greshki(zab))

    def test_chist_tekst(self):
        zab = proverki.proveri_tekst("Болката в кръста след 8 часа седене", "zaglavie", "т", CFG)
        self.assertFalse(proverki.ima_greshki(zab), zab)

    def test_ceni_zabraneni(self):
        for t in ["Преглед само за 25 €", "Консултация 40 лв.", "Безплатна консултация", "Ниска цена"]:
            self.assertTrue(proverki.ima_greshki(proverki.pravila(t, "т", CFG)), t)

    def test_zdravni_pravila(self):
        for t in ["Теб те боли кръстът?", "Излекуваме болката", "Гарантирано без болка", "Твоята болка в кръста"]:
            self.assertTrue(proverki.ima_greshki(proverki.pravila(t, "т", CFG)), t)

    def test_kopi_555(self):
        kopi = {
            "osnovni": [f"Текст номер {i} за кръста." for i in range(5)],
            "zaglaviya": [f"Заглавие {i}" for i in range(5)],
            "opisaniya": [f"Описание {i}" for i in range(5)],
        }
        self.assertFalse(proverki.ima_greshki(proverki.proveri_kopi(kopi, CFG)))
        kopi["zaglaviya"][1] = kopi["zaglaviya"][0]
        self.assertTrue(proverki.ima_greshki(proverki.proveri_kopi(kopi, CFG)))
        kopi["zaglaviya"].pop()
        self.assertTrue(proverki.ima_greshki(proverki.proveri_kopi(kopi, CFG)))

    def test_banner_akcent(self):
        b = {"kod": "A1", "zaglavie": "Болката в кръста", "akcent": "врата"}
        self.assertTrue(proverki.ima_greshki(proverki.proveri_banner(b, CFG)))


class Ikonomika(unittest.TestCase):
    def test_tavan(self):
        ik = CFG["ikonomika"]
        ochakvan = ik["prihod_nov_pacient_60d"] * ik["dyal_za_reklama"] * ik["saobshtenie_kam_chas"] * ik["chas_kam_doshal"]
        self.assertAlmostEqual(CFG.tavan_rezultat, round(ochakvan, 2), places=2)


def red(razhod, rez, impr=2000, ctr=1.2, chestota=1.5):
    return {"ime": "x", "adset": "", "id": "", "razhod": razhod, "rezultati": rez,
            "cena_rezultat": round(razhod / rez, 2) if rez else None,
            "pokazvania": impr, "chestota": chestota, "ctr": ctr}


class Pravila3714(unittest.TestCase):
    T = 10.0

    def test_rano(self):
        self.assertEqual(otchet.reshi(red(5, 0), 1, self.T)[0], otchet.RANO)

    def test_izgoryal_budjet(self):
        self.assertEqual(otchet.reshi(red(25, 0), 2, self.T)[0], otchet.SPRI)

    def test_den3_slab_huk(self):
        self.assertEqual(otchet.reshi(red(8, 1, impr=3000, ctr=0.3), 3, self.T)[0], otchet.SPRI)

    def test_den7_umnozhi(self):
        self.assertEqual(otchet.reshi(red(30, 6), 7, self.T)[0], otchet.UMNOZHI)

    def test_den7_spri_skapo(self):
        self.assertEqual(otchet.reshi(red(32, 2), 7, self.T)[0], otchet.SPRI)

    def test_den7_ostavi(self):
        self.assertEqual(otchet.reshi(red(27, 3), 7, self.T)[0], otchet.OSTAVI)

    def test_den14_umora(self):
        self.assertEqual(otchet.reshi(red(36, 3, chestota=3.4), 14, self.T)[0], otchet.SPRI)


class SPartida(unittest.TestCase):
    """Цяла партида във временна папка: матрица → смета → банери → видео → копи → план за Meta."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patch = mock.patch.multiple(config, PARTIDI=self.tmp / "partidi", OTCHETI=self.tmp / "otcheti")
        self.patch.start()
        mock.patch.object(partida, "PARTIDI", self.tmp / "partidi").start()
        mock.patch.object(otchet, "OTCHETI", self.tmp / "otcheti").start()

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _popalni(self, p):
        from PIL import Image
        snimka = p / "snimki" / "foto.jpg"
        Image.new("RGB", (1200, 900), "#887766").save(snimka)
        m = partida.matrica(p)
        agli = ["болка", "доказателство", "механизъм"]
        oform = ["snimka", "bolka", "dokazatelstvo", "mehanizam"]
        for i, a in enumerate(m["adseti"]):
            a["agal"] = agli[i]
            a["ime"] = f"PF · {a['kod']} · {agli[i]}"
            for j, b in enumerate(a["banneri"]):
                b.update({"oformlenie": oform[j], "snimka": "snimki/foto.jpg",
                          "zaglavie": "Болката в кръста след 8 часа седене", "akcent": "8 часа седене",
                          "stapki": ["Разговор", "Тестове", "План"]})
            for v in a["video"]:
                v.update({"huk": "Болката в кръста след 8 часа седене",
                          "glas_tekst": "Болката в кръста след 8 часа седене има причина. Ето какво правим на прегледа.",
                          "priziv": "Запиши час", "kadri": [{"fail": "snimki/foto.jpg", "sek": 1.5}]})
        m["kopi"] = {
            "osnovni": [f"Болката в кръста след седене, вариант {i}. Пиши ни." for i in range(5)],
            "zaglaviya": [f"Преглед в Пловдив {i}" for i in range(5)],
            "opisaniya": [f"Идваме и у дома {i}" for i in range(5)],
        }
        config.pishi_json(p / "matrica.json", m)

    def test_cyal_pat(self):
        p = partida.nova("болка в кръста", CFG)
        self.assertTrue((p / "matrica.json").exists())
        self._popalni(p)
        zab = smetka.proveri_matrica(p, CFG)
        self.assertFalse(proverki.ima_greshki(zab), [str(z) for z in zab])
        s = smetka.presmetni(p, CFG)
        self.assertEqual(s["reklama_na_den"], 3 * CFG["test"]["dneven_budjet_na_adset"])

        for _, b in partida.vsichki_banneri(partida.matrica(p)):
            for f in banneri.FORMATI:
                banneri.napravi(b, f, CFG, p, p / "banneri" / f"{b['kod']}_{f}.png")
        self.assertEqual(len(list((p / "banneri").glob("*_4x5.png"))), 12)

        if shutil.which("ffmpeg"):
            from mashina import video
            _, v = next(partida.vsichki_video(partida.matrica(p)))
            izhod = video.sglobi(v, p, CFG)
            self.assertGreater(video.prodalzhitelnost(izhod), 3.5)
            for _, v in partida.vsichki_video(partida.matrica(p)):
                if v["kod"] != "AV1":
                    shutil.copy(izhod, p / "video" / f"{v['kod']}.mp4")
                    shutil.copy(p / "video" / "AV1_korica.jpg", p / "video" / f"{v['kod']}_korica.jpg")

            plan = M.napravi_plan(p, CFG)
            self.assertEqual(plan["obshto_reklami"], 15)
            self.assertEqual(plan["lipsvat_failove"], [])
            self.assertEqual(plan["status"], "PAUSED")

        # качването без Стоп Б е забранено
        with self.assertRaises(config.MashinaGreshka):
            M.kachi(p, CFG)

    def test_otchet_ot_csv(self):
        p = partida.nova("тест отчет", CFG)
        partida.otbeleji(p, "pusnata", True)
        csv_pat = self.tmp / "export.csv"
        with csv_pat.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Ad name", "Ad set name", "Amount spent (EUR)", "Results", "Impressions", "CTR (all)", "Frequency"])
            w.writerow(["PF_A1", "A", "30", "8", "5000", "1.5", "1.4"])
            w.writerow(["PF_A2", "A", "40", "0", "4000", "0.4", "1.6"])
        redove = otchet.ot_csv(csv_pat, "messages")
        izhod, redove = otchet.napravi(p, CFG, redove, den=7)
        reshenia = {r["ime"]: r["reshenie"] for r in redove}
        self.assertEqual(reshenia["PF_A1"], otchet.UMNOZHI)
        self.assertEqual(reshenia["PF_A2"], otchet.SPRI)
        self.assertTrue((self.tmp / "otcheti" / "dnevnik.csv").exists())


class KodBezSmeseniBukvi(unittest.TestCase):
    """Машината проверява и себе си: никакви смесени букви в кода."""

    def test_kod(self):
        for f in (KOREN / "paket" / "mashina").glob("*.py"):
            for i, red_ in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                red_ = re.sub(r"\\[a-zA-Z]", " ", red_)  # \b, \s в регулярни изрази
                zab = [z for z in proverki.bukva_po_bukva(red_, f"{f.name}:{i}") if z.nivo == "greshka"]
                self.assertFalse(zab, [str(z) for z in zab])


class Cli(unittest.TestCase):
    def test_pomosht(self):
        r = subprocess.run([str(KOREN / "mashina")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("doktor", r.stdout)


if __name__ == "__main__":
    unittest.main()


class GlasOtTelefona(unittest.TestCase):
    """Безплатният режим: гласът е m4a от iPhone."""

    def test_m4a(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("няма ffmpeg")
        from PIL import Image
        from mashina import video
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "video").mkdir()
            Image.new("RGB", (800, 600), "#556655").save(tmp / "f.jpg")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=200:duration=4",
                            "-c:a", "aac", str(tmp / "video" / "T1_glas.m4a")], check=True)
            self.assertEqual(video.nameri_glas(tmp, "T1").suffix, ".m4a")
            v = {"kod": "T1", "glas_tekst": "Една две три четири пет шест", "priziv": "Запиши час",
                 "kadri": [{"fail": "f.jpg", "sek": 1}]}
            izhod = video.sglobi(v, tmp, CFG)
            r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name",
                                "-of", "csv=p=0", str(izhod)], capture_output=True, text=True)
            self.assertIn("aac", r.stdout)
            self.assertGreaterEqual(video.prodalzhitelnost(izhod), 4.0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_kie_izklyuchen(self):
        self.assertFalse(CFG.get("kie", "vkluchen", True))
        r = subprocess.run([str(KOREN / "mashina"), "kie", "krediti"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("безплатен режим", r.stderr)
