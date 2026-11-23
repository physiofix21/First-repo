"""Минимален HTTP клиент без външни библиотеки (urllib)."""
from __future__ import annotations

import json
import mimetypes
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import MashinaGreshka


def zayavka(metod: str, url: str, *, params: dict | None = None, json_telo=None, forma: dict | None = None,
            failove: dict | None = None, headers: dict | None = None, timeout: int = 120):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    h = dict(headers or {})
    data = None
    if json_telo is not None:
        data = json.dumps(json_telo).encode()
        h["Content-Type"] = "application/json"
    elif failove:
        granica = uuid.uuid4().hex
        chasti = []
        for k, v in (forma or {}).items():
            chasti.append(f'--{granica}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for k, pat in failove.items():
            pat = Path(pat)
            tip = mimetypes.guess_type(pat.name)[0] or "application/octet-stream"
            chasti.append(
                f'--{granica}\r\nContent-Disposition: form-data; name="{k}"; filename="{pat.name}"\r\n'
                f"Content-Type: {tip}\r\n\r\n".encode() + pat.read_bytes() + b"\r\n")
        chasti.append(f"--{granica}--\r\n".encode())
        data = b"".join(chasti)
        h["Content-Type"] = f"multipart/form-data; boundary={granica}"
    elif forma is not None:
        data = urllib.parse.urlencode(forma).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, method=metod, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            telo = r.read()
    except urllib.error.HTTPError as e:
        telo = e.read()
        try:
            detail = json.loads(telo)
        except ValueError:
            detail = telo[:300].decode(errors="replace")
        raise MashinaGreshka(f"{metod} {url.split('?')[0]} → HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise MashinaGreshka(f"Няма връзка с {urllib.parse.urlparse(url).netloc}: {e.reason}") from None
    try:
        return json.loads(telo)
    except ValueError:
        return telo


def svali(url: str, pat: Path, timeout: int = 300) -> Path:
    pat.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            pat.write_bytes(r.read())
    except urllib.error.URLError as e:
        raise MashinaGreshka(f"Не мога да сваля {url}: {e}") from None
    return pat
