"""KIE.AI: снимки (Nano Banana), видео кадри (Veo 3) и глас (ElevenLabs).

Машината пише само този клиент. AI-ят в папката не пише свой код за KIE:
вика `./mashina kie ...` (правило от CLAUDE.md).

Всяко генериране харчи кредити, затова всяка функция тук изисква
партидата да е минала Стоп А (`./mashina smetka --da`).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import MashinaGreshka
from .http import svali, zayavka


class Kie:
    def __init__(self, cfg):
        self.cfg = cfg
        self.kluch = cfg.env.get("KIE_API_KEY", "")
        self.url = cfg.get("kie", "api_url", "https://api.kie.ai").rstrip("/")

    def _h(self):
        if not self.kluch:
            raise MashinaGreshka("Няма KIE_API_KEY в .env. Виж START.md → урок 02.")
        return {"Authorization": f"Bearer {self.kluch}"}

    # ── сметка ──
    def krediti(self) -> float:
        r = zayavka("GET", f"{self.url}/api/v1/chat/credit", headers=self._h(), timeout=30)
        if isinstance(r, dict) and r.get("code") == 200:
            return float(r.get("data") or 0)
        raise MashinaGreshka(f"KIE не върна кредитите: {r}")

    # ── обща задача (Market API: jobs/createTask) ──
    def _zadacha(self, model: str, vhod: dict) -> str:
        r = zayavka("POST", f"{self.url}/api/v1/jobs/createTask", headers=self._h(),
                    json_telo={"model": model, "input": vhod})
        if not isinstance(r, dict) or r.get("code") != 200:
            raise MashinaGreshka(f"KIE отказа задачата ({model}): {r}")
        return r["data"]["taskId"]

    def _chakai(self, task_id: str, maks_sek: int = 600) -> list[str]:
        krai = time.time() + maks_sek
        pauza = 4
        while time.time() < krai:
            r = zayavka("GET", f"{self.url}/api/v1/jobs/recordInfo", params={"taskId": task_id},
                        headers=self._h(), timeout=30)
            d = (r or {}).get("data") or {}
            sast = (d.get("state") or "").lower()
            if sast == "success":
                rez = d.get("resultJson") or "{}"
                rez = json.loads(rez) if isinstance(rez, str) else rez
                urls = rez.get("resultUrls") or rez.get("resultUrl") or []
                return [urls] if isinstance(urls, str) else list(urls)
            if sast in ("fail", "failed", "error"):
                raise MashinaGreshka(f"KIE задача {task_id} се провали: {d.get('failMsg') or d}")
            time.sleep(pauza)
            pauza = min(pauza * 1.5, 15)
        raise MashinaGreshka(f"KIE задача {task_id} не приключи за {maks_sek} сек. Провери в kie.ai → Logs.")

    # ── снимка ──
    def snimka(self, prompt: str, izhod: Path, format_: str = "4:5", vhodni: list[str] | None = None) -> Path:
        """Генерира изображение. С `vhodni` (публични URL на твои снимки) редактира/доразвива снимката."""
        if vhodni:
            model = self.cfg.get("kie", "model_redakcia", "google/nano-banana-edit")
            vhod = {"prompt": prompt, "image_urls": vhodni, "output_format": "png", "image_size": format_}
        else:
            model = self.cfg.get("kie", "model_snimka", "google/nano-banana")
            vhod = {"prompt": prompt, "output_format": "png", "image_size": format_}
        urls = self._chakai(self._zadacha(model, vhod))
        if not urls:
            raise MashinaGreshka("KIE не върна изображение")
        return svali(urls[0], izhod)

    # ── глас ──
    def glas(self, tekst: str, izhod: Path) -> Path:
        model = self.cfg.get("kie", "model_glas", "elevenlabs/text-to-speech-multilingual-v2")
        vhod = {"text": tekst, "voice": self.cfg.get("kie", "glas", "Rachel"),
                "stability": 0.5, "similarity_boost": 0.75, "speed": 1.0}
        urls = self._chakai(self._zadacha(model, vhod), maks_sek=300)
        if not urls:
            raise MashinaGreshka("KIE не върна аудио")
        return svali(urls[0], izhod)

    # ── видео кадър (Veo 3) ──
    def video(self, prompt: str, izhod: Path, format_: str = "9:16", snimka_url: str | None = None) -> Path:
        telo = {"prompt": prompt, "model": self.cfg.get("kie", "model_video", "veo3_fast"), "aspectRatio": format_}
        if snimka_url:
            telo["imageUrls"] = [snimka_url]
        r = zayavka("POST", f"{self.url}/api/v1/veo/generate", headers=self._h(), json_telo=telo)
        if not isinstance(r, dict) or r.get("code") != 200:
            raise MashinaGreshka(f"KIE Veo отказа: {r}")
        task_id = r["data"]["taskId"]
        krai = time.time() + 900
        while time.time() < krai:
            s = zayavka("GET", f"{self.url}/api/v1/veo/record-info", params={"taskId": task_id},
                        headers=self._h(), timeout=30)
            d = (s or {}).get("data") or {}
            flag = d.get("successFlag")
            if flag == 1:
                resp = d.get("response") or {}
                urls = resp.get("resultUrls") or []
                if isinstance(urls, str):
                    urls = json.loads(urls)
                return svali(urls[0], izhod)
            if flag in (2, 3):
                raise MashinaGreshka(f"Veo задача {task_id} се провали: {d.get('errorMessage') or d}")
            time.sleep(10)
        raise MashinaGreshka(f"Veo задача {task_id} не приключи за 15 мин.")
