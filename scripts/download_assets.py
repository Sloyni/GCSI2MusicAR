"""Fetch the official model and the attributed piano recordings, once."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
SAMPLE_URL = "https://tonejs.github.io/audio/salamander/"


def download(item):
    relative, url = item
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size < 1024:
        temporary = path.with_suffix(path.suffix + ".part")
        request = urllib.request.Request(url, headers={"User-Agent": "MusicAR/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read()
            if len(data) < 1024:
                raise RuntimeError(f"Fichier incomplet: {relative}")
            temporary.write_bytes(data)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    data = path.read_bytes()
    print(f"OK {relative} ({len(data):,} octets)", flush=True)
    return {"file": relative, "url": url, "bytes": len(data), "sha256": sha256(data).hexdigest()}


def main():
    samples = [f"{note}{octave}" for octave in range(3, 7) for note in ("C", "Ds", "Fs", "A")] + ["C7"]
    items = [("assets/models/hand_landmarker.task", MODEL_URL)]
    items.extend((f"assets/audio/{name}.mp3", SAMPLE_URL + name + ".mp3") for name in samples)
    guitar_url="https://raw.githubusercontent.com/nbrosowsky/tonejs-instruments/master/samples/guitar-acoustic/"
    items.extend((f"assets/audio/guitar/{name}.mp3",guitar_url+name+".mp3")
                 for name in ["E2","A2","D3","G3","B3","E4","G4","B4"])
    vision_url="https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/"
    items.append(("web/vendor/vision_bundle.mjs",vision_url+"vision_bundle.mjs"))
    items.extend(("web/vendor/wasm/"+name,vision_url+"wasm/"+name) for name in
                 ["vision_wasm_internal.js","vision_wasm_internal.wasm",
                  "vision_wasm_nosimd_internal.js","vision_wasm_nosimd_internal.wasm"])
    with ThreadPoolExecutor(max_workers=6) as pool:
        manifest = list(pool.map(download, items))
    (ROOT / "assets/manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Modèle, piano et guitare prêts. Utilisation hors ligne disponible.", flush=True)


if __name__ == "__main__":
    main()

