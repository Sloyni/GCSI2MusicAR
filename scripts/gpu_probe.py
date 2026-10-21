"""Run our own GPU diagnostic page in a hidden WebView; no webcam is captured."""
import argparse
import json
from pathlib import Path
import threading
import time
import urllib.request
import uuid

import webview


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--delegate",choices=["GPU","CPU","HYBRID"],default="HYBRID")
    parser.add_argument("--audio",action="store_true",help="Vérifier les banques audio par rendu hors ligne")
    args=parser.parse_args()
    artifacts=Path(__file__).resolve().parents[1]/"artifacts"
    artifacts.mkdir(exist_ok=True)
    reference=artifacts/"mediapipe-right-hands.jpg"
    if not args.audio and not reference.is_file():
        with urllib.request.urlopen("https://storage.googleapis.com/mediapipe-assets/right_hands.jpg",timeout=30) as response:
            reference.write_bytes(response.read())
    base=f"http://127.0.0.1:{args.port}"
    nonce=uuid.uuid4().hex
    result={"ok":False,"error":"GPU probe timeout"}
    page="audio-diagnostic.html" if args.audio else "gpu-diagnostic.html"
    window=webview.create_window("MusicAR — diagnostic",f"{base}/static/{page}?nonce={nonce}&delegate={args.delegate}",
                                 width=400,height=300,hidden=True)
    def monitor():
        nonlocal result
        for _ in range(120):
            try:
                with urllib.request.urlopen(base+"/api/diagnostic/gpu",timeout=2) as response:
                    status=json.load(response)
                if status.get("nonce")==nonce:
                    result=status;break
            except Exception:pass
            time.sleep(.5)
        window.destroy()
    webview.start(monitor,gui="edgechromium",private_mode=True)
    print(json.dumps(result,indent=2),flush=True)
    filename="audio-validation.json" if args.audio else f"{args.delegate.lower()}-web-validation.json"
    output=artifacts/filename
    output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    if not result.get("ok"):raise SystemExit(1)


if __name__=="__main__":main()
