"""One camera worker; latest-frame streaming and bounded, ordered note events."""
from collections import deque
import logging
from pathlib import Path
import threading
import time

from .gestures import FINGERS, Settings, InstrumentTracker

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]


class CameraEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.settings = Settings()
        self.revision = 0
        self.tracker = InstrumentTracker(self.settings)
        self.thread = None
        self.stop_event = threading.Event()
        self.jpeg = b""
        self.frame_id = 0
        self.event_id = 0
        self.events = deque(maxlen=1024)
        self.status = "idle"
        self.message = "La caméra est en veille."
        self.hands = []
        self.fps = 0.0
        self.inference_ms = 0.0
        self.width, self.height = 960, 540
        self.index = 0
        self.external_owner = None
        self.compute = "CPU Python"
        self._identities = {}
        self._next_identity = 0

    def _events(self, events):
        for event in events:
            if event["kind"] == "style":
                self.revision += 1
            self.event_id += 1
            self.events.append({**event, "id": self.event_id})

    def configure(self, settings):
        with self.lock:
            self._events(self.tracker.reset(settings))
            self.settings = settings
            self.revision += 1
            return {"config": settings.model_dump(), "layout": self.tracker.layout.dump(), "revision": self.revision}

    def panic(self):
        with self.lock:
            self._events(self.tracker.reset())

    def start(self, index=0):
        with self.lock:
            if self.external_owner is not None:
                raise RuntimeError("La caméra Turbo est active. Arrêtez-la avant de changer de mode.")
            if self.thread and self.thread.is_alive():
                if self.index == index and self.status != "stopping":
                    return
                raise RuntimeError("Arrêtez la caméra active avant de changer de source.")
            model = ROOT / "assets/models/hand_landmarker.task"
            if not model.is_file():
                raise RuntimeError("Modèle absent. Lancez scripts/download_assets.py.")
            self.index = index
            self.compute = "CPU Python"
            self.stop_event.clear()
            self.status = "starting"
            self.message = "Connexion à la caméra…"
            self.jpeg = b""
            self.hands = []
            self._identities.clear()
            self._events(self.tracker.reset())
            self.thread = threading.Thread(target=self._run, name="MusicAR-camera", daemon=True)
            self.thread.start()

    def stop(self):
        with self.lock:
            self.external_owner = None
            self.stop_event.set()
            thread = self.thread
            if thread and thread.is_alive():
                self.status = "stopping"
                self.message = "Fermeture de la caméra…"
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5)
        with self.lock:
            self._events(self.tracker.reset())
            self.hands = []
            self.jpeg = b""
            self.frame_id += 1
            self.fps = 0
            if not thread or not thread.is_alive():
                self.status = "idle"
                self.message = "La caméra est en veille."

    def snapshot(self, after=0):
        with self.lock:
            return {"status": self.status, "message": self.message, "frame_id": self.frame_id,
                    "event_id": self.event_id, "events": [e.copy() for e in self.events if e["id"] > after],
                    "hands": self.hands, "fps": round(self.fps, 1),
                    "inference_ms": round(self.inference_ms, 1), "width": self.width, "height": self.height,
                    "revision": self.revision, "guitar": self.tracker.guitar,
                    "performance":self.tracker.performance, "compute":self.compute}, self.jpeg

    def claim_external(self, owner):
        with self.lock:
            if self.external_owner not in (None,owner) or (self.thread and self.thread.is_alive()):
                raise RuntimeError("Une caméra est déjà active dans un autre studio.")
            self.external_owner=owner
            self._identities.clear()
            self._events(self.tracker.reset())
            self.jpeg=b""

    def publish_external(self,owner,packet):
        with self.lock:
            if self.external_owner!=owner:raise RuntimeError("Session caméra arrêtée")
            now=time.monotonic()
            after=self.event_id
            self.status="running"
            self.message="Caméra directe et suivi accéléré."
            self.compute=packet["compute"]
            self.width,self.height=packet["width"],packet["height"]
            self.fps=packet["fps"]
            self.inference_ms=packet["inference_ms"]
            self.hands=self._assign(packet["hands"],now)
            points=[{"hand":hand["id"],"finger":name,"x":hand["landmarks"][FINGERS[name]][0],
                     "y":hand["landmarks"][FINGERS[name]][1]}
                    for hand in self.hands for name in self.settings.fingers]
            self._events(self.tracker.update(points,now,self.hands,self.width,self.height))
            self.frame_id+=1
            return self.snapshot(after)[0]

    def release_external(self,owner):
        with self.lock:
            if self.external_owner!=owner:return
            self.external_owner=None
            self._events(self.tracker.reset())
            self.hands=[]
            self.status="idle"
            self.message="La caméra est en veille."
            self.fps=0
            self.frame_id+=1

    def _assign(self, detected, now):
        # Associate wrists by proximity, not the order returned by MediaPipe.
        self._identities = {key: value for key, value in self._identities.items() if now - value[2] < .35}
        candidates = []
        for i, hand in enumerate(detected):
            wrist = hand["landmarks"][0]
            for key, (previous, label, _) in self._identities.items():
                distance = (wrist[0] - previous[0]) ** 2 + (wrist[1] - previous[1]) ** 2
                if distance < .16:
                    candidates.append((distance + (0 if label == hand["label"] else .01), i, key))
        assigned, used = {}, set()
        for _, i, key in sorted(candidates):
            if i not in assigned and key not in used:
                assigned[i] = key
                used.add(key)
        for i, hand in enumerate(detected):
            if i not in assigned:
                self._next_identity += 1
                assigned[i] = self._next_identity
            hand["id"] = assigned[i]
            self._identities[hand["id"]] = (hand["landmarks"][0], hand["label"], now)
        return detected

    def _run(self):
        cap = detector = None
        failed = False
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            # DirectShow is more reliable for USB cameras on Windows.
            import sys
            cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(self.index)
            if not cap.isOpened():
                raise RuntimeError("Caméra indisponible. Vérifiez la source, les permissions Windows ou une autre application qui l'utilise.")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(ROOT / "assets/models/hand_landmarker.task")),
                running_mode=vision.RunningMode.VIDEO, num_hands=2,
                min_hand_detection_confidence=.55, min_hand_presence_confidence=.55,
                min_tracking_confidence=.55)
            detector = vision.HandLandmarker.create_from_options(options)
            previous = time.monotonic()
            timestamp = 0
            failures = 0
            with self.lock:
                self.status = "running"
                self.message = "Placez les cercles de vos doigts sur les touches pour jouer."
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    failures += 1
                    if failures > 12:
                        raise RuntimeError("Flux caméra interrompu. Reconnectez la caméra puis réessayez.")
                    self.stop_event.wait(.03)
                    continue
                failures = 0
                with self.lock:
                    mirror = self.settings.mirror
                    revision = self.revision
                if mirror:
                    frame = cv2.flip(frame, 1)
                if frame.shape[1] > 960:
                    frame = cv2.resize(frame, (960, round(frame.shape[0] * 960 / frame.shape[1])))
                start = time.monotonic()
                timestamp = max(timestamp + 1, int(start * 1000))
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                                                             data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), timestamp)
                inference_ms = (time.monotonic() - start) * 1000
                detected = []
                for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
                    detected.append({"label": handedness[0].category_name,
                                     "confidence": round(handedness[0].score, 3),
                                     "landmarks": [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in landmarks]})
                now = time.monotonic()
                hands = self._assign(detected, now)
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
                with self.lock:
                    if revision == self.revision:
                        points = [{"hand": hand["id"], "finger": name,
                                   "x": hand["landmarks"][FINGERS[name]][0],
                                   "y": hand["landmarks"][FINGERS[name]][1]}
                                  for hand in hands for name in self.settings.fingers]
                        self._events(self.tracker.update(points, now, hands, frame.shape[1], frame.shape[0]))
                    self.hands = hands
                    self.inference_ms = inference_ms
                    self.fps = self.fps * .85 + (1 / max(.001, now - previous)) * .15
                    self.height, self.width = frame.shape[:2]
                    if ok:
                        self.jpeg = encoded.tobytes()
                        self.frame_id += 1
                previous = now
        except Exception as error:
            failed = True
            LOG.exception("Camera worker failed")
            with self.lock:
                self.status = "error"
                self.message = str(error)
        finally:
            if cap is not None:
                cap.release()
            if detector is not None:
                detector.close()
            with self.lock:
                self._events(self.tracker.reset())
                self.hands = []
                self.jpeg = b""
                self.frame_id += 1
                if not failed:
                    self.status = "idle"
                    self.message = "La caméra est en veille."

