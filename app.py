"""Start a local Python service in an embedded desktop window."""
import argparse
import errno
import json
import logging
from pathlib import Path
import threading
import socket
import time
import urllib.request
import webbrowser

import uvicorn


def probe_service(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health",timeout=.6) as response:
            body=json.load(response)
            return isinstance(body,dict) and body.get("app")=="MusicAR"
    except (OSError,ValueError):
        return False


def prepare_service(port):
    """Reuse MusicAR; otherwise reserve a socket, avoiding a bind/start race."""
    if probe_service(port):
        return None,f"http://127.0.0.1:{port}"
    listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1",port))
    except OSError as error:
        if error.errno not in (errno.EADDRINUSE,10048):
            listener.close()
            raise
        listener.bind(("127.0.0.1",0))
    listener.listen(2048)
    actual_port=listener.getsockname()[1]
    return listener,f"http://127.0.0.1:{actual_port}"


def main():
    parser = argparse.ArgumentParser(description="MusicAR — studio musical en réalité augmentée")
    parser.add_argument("--browser", action="store_true", help="Ouvrir dans le navigateur au lieu de la fenêtre intégrée")
    parser.add_argument("--headless", action="store_true", help="Service local uniquement")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    logdir = Path(__file__).resolve().parent / "logs"
    logdir.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.FileHandler(logdir / "musicar.log", encoding="utf-8"), logging.StreamHandler()])
    listener,url=prepare_service(args.port)
    server=thread=None
    if listener is not None:
        server = uvicorn.Server(uvicorn.Config("musicar.server:app", host="127.0.0.1", port=listener.getsockname()[1], log_level="warning"))
    if args.headless:
        print(f"MusicAR disponible sur {url}", flush=True)
        if server:server.run(sockets=[listener])
        else:print("Instance MusicAR déjà active : réutilisation sans second serveur.",flush=True)
        return
    if server:
        thread = threading.Thread(target=lambda:server.run(sockets=[listener]), daemon=True)
        thread.start()
        for _ in range(100):
            if not thread.is_alive():raise SystemExit("Le service a échoué. Consultez logs/musicar.log.")
            if server.started:break
            time.sleep(.10)
        else:raise SystemExit("Démarrage du serveur trop long. Consultez logs/musicar.log.")
    try:
        if args.browser:
            webbrowser.open(url)
            print(f"MusicAR disponible sur {url}. Ctrl+C pour quitter.", flush=True)
            if thread:
                while thread.is_alive():thread.join(.5)
        else:
            import webview
            webview.create_window("MusicAR — Votre studio augmenté", url, width=1440, height=940,
                                  min_size=(1024, 720), background_color="#101113")
            webview.start(gui="edgechromium" if __import__("sys").platform == "win32" else None,
                          private_mode=False,storage_path=str(logdir.parent / ".runtime/webview"))
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.should_exit = True
            thread.join(timeout=8)
            listener.close()
        elif not args.browser:
            try:
                urllib.request.urlopen(urllib.request.Request(url+"/api/camera/stop",data=b"",method="POST"),timeout=5).close()
            except OSError:pass


if __name__ == "__main__":
    main()
