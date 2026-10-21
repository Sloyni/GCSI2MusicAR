from contextlib import asynccontextmanager
import asyncio
import json
from pathlib import Path
import struct
from typing import Annotated, Literal
import uuid

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .engine import CameraEngine
from .gestures import Settings

ROOT = Path(__file__).resolve().parents[1]
engine = CameraEngine()


@asynccontextmanager
async def lifespan(app):
    yield
    await asyncio.to_thread(engine.stop)


app = FastAPI(title="MusicAR", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


def local_origin(origin: str, host: str) -> bool:
    # A different port is a different origin, even on localhost.
    return origin in (f"http://{host}", f"https://{host}")


@app.middleware("http")
async def protect_local_camera(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and not local_origin(origin, request.headers.get("host", "")):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Origine non autorisée"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/static/") or request.url.path=="/":
        response.headers["Cache-Control"]="no-cache"
    return response


@app.get("/")
def index():
    return FileResponse(ROOT / "web/index.html")


@app.get("/api/health")
def health():
    state, _ = engine.snapshot()
    return {"app": "MusicAR", "version": "0.2.0", "camera": state["status"],
            "interaction": "contact", "guitar_ready": all((ROOT / f"assets/audio/guitar/{name}.mp3").is_file()
                for name in ("E2","A2","D3","G3","B3","E4","G4","B4")),
            "gpu_ready":(ROOT / "web/vendor/wasm/vision_wasm_internal.wasm").is_file(),
            "model_ready": (ROOT / "assets/models/hand_landmarker.task").is_file(),
            "samples_ready": all((ROOT / f"assets/audio/{name}.mp3").is_file()
                                 for name in [f"{n}{o}" for o in range(3, 7) for n in ("C", "Ds", "Fs", "A")] + ["C7"])}


@app.get("/api/config")
def config():
    with engine.lock:
        return {"config": engine.settings.model_dump(), "layout": engine.tracker.layout.dump(), "revision": engine.revision}


@app.put("/api/config")
def configure(settings: Settings):
    return engine.configure(settings)


class CameraRequest(BaseModel):
    index: int = Field(default=0, ge=0, le=9)


@app.post("/api/camera/start")
def camera_start(request: CameraRequest):
    try:
        engine.start(request.index)
    except RuntimeError as error:
        raise HTTPException(409, detail=str(error)) from error
    return {"status": "starting"}


@app.post("/api/camera/stop")
async def camera_stop():
    await asyncio.to_thread(engine.stop)
    return {"status": engine.status}


@app.post("/api/panic")
def panic():
    engine.panic()
    return {"ok": True}


@app.websocket("/ws")
async def stream(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin and not local_origin(origin, websocket.headers.get("host", "")):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    # A new listener should not replay notes from an earlier session.
    after = engine.event_id
    last_frame = -1
    revision = -1
    heartbeat = 0
    try:
        while True:
            state, jpeg = engine.snapshot(after)
            now = asyncio.get_running_loop().time()
            if state["frame_id"] != last_frame or state["events"] or now - heartbeat > .35 or state["revision"] != revision:
                if state["revision"] != revision:
                    state["settings"] = config()
                    revision = state["revision"]
                metadata = json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                await asyncio.wait_for(websocket.send_bytes(struct.pack(">I", len(metadata)) + metadata + jpeg), timeout=2)
                after = state["event_id"]
                last_frame = state["frame_id"]
                heartbeat = now
            await asyncio.sleep(.016)
    except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError):
        pass


Coord = Annotated[float,Field(allow_inf_nan=False,ge=-4,le=4)]


class BrowserHand(BaseModel):
    label: Literal["Left","Right"]
    confidence: float = Field(ge=0,le=1,allow_inf_nan=False)
    landmarks: list[Annotated[list[Coord],Field(min_length=3,max_length=3)]] = Field(min_length=21,max_length=21)


class BrowserFrame(BaseModel):
    hands: list[BrowserHand] = Field(max_length=2)
    width: int = Field(ge=160,le=3840)
    height: int = Field(ge=120,le=2160)
    fps: float = Field(ge=0,le=240,allow_inf_nan=False)
    inference_ms: float = Field(ge=0,le=10000,allow_inf_nan=False)
    compute: str = Field(max_length=240)


@app.websocket("/ws/hands")
async def direct_hands(websocket: WebSocket):
    origin=websocket.headers.get("origin")
    if origin and not local_origin(origin,websocket.headers.get("host","")):
        await websocket.close(code=1008);return
    await websocket.accept()
    owner=uuid.uuid4().hex
    try:
        engine.claim_external(owner)
        while True:
            data=await asyncio.wait_for(websocket.receive_json(),timeout=1)
            packet=BrowserFrame.model_validate(data)
            state=engine.publish_external(owner,packet.model_dump())
            # No frame encoding, no polling timer: send note events immediately.
            await websocket.send_json(state)
    except (WebSocketDisconnect,asyncio.TimeoutError):
        pass
    except Exception as error:
        try:await websocket.send_json({"error":str(error)})
        except Exception:pass
        try:await websocket.close(code=1008)
        except Exception:pass
    finally:
        engine.release_external(owner)


gpu_diagnostic={}


@app.websocket("/ws/infer")
async def hybrid_inference(websocket:WebSocket):
    origin=websocket.headers.get("origin")
    if origin and not local_origin(origin,websocket.headers.get("host","")):
        await websocket.close(code=1008);return
    await websocket.accept()
    owner=uuid.uuid4().hex
    detector=None
    try:
        import cv2
        import mediapipe as mp
        import numpy as np
        import time
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        def create_detector():
            return vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=str(ROOT / "assets/models/hand_landmarker.task")),
                running_mode=vision.RunningMode.VIDEO,num_hands=2,min_hand_detection_confidence=.5,
                min_hand_presence_confidence=.5,min_tracking_confidence=.5))
        detector=await asyncio.to_thread(create_detector)
        engine.claim_external(owner)
        timestamp=0
        while True:
            packet=await asyncio.wait_for(websocket.receive_bytes(),timeout=2)
            if len(packet)<8 or len(packet)>1_000_000:raise ValueError("Image invalide")
            length=struct.unpack(">I",packet[:4])[0]
            if length>4096 or length>=len(packet)-4:raise ValueError("En-tête invalide")
            header=json.loads(packet[4:4+length])
            width,height=int(header["width"]),int(header["height"])
            if not (160<=width<=3840 and 120<=height<=2160):raise ValueError("Dimensions invalides")
            with engine.lock:mirror=engine.settings.mirror
            timestamp=max(timestamp+1,int(time.monotonic()*1000))
            def infer():
                image=cv2.imdecode(np.frombuffer(packet[4+length:],dtype=np.uint8),cv2.IMREAD_COLOR)
                if image is None:raise ValueError("JPEG invalide")
                if image.shape[1]>960:image=cv2.resize(image,(640,round(image.shape[0]*640/image.shape[1])))
                if mirror:image=cv2.flip(image,1)
                start=time.perf_counter()
                result=detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)),timestamp)
                duration=(time.perf_counter()-start)*1000
                hands=[{"label":categories[0].category_name,"confidence":categories[0].score,
                        "landmarks":[[p.x,p.y,p.z] for p in points]}
                       for points,categories in zip(result.hand_landmarks,result.handedness)]
                return hands,duration
            hands,duration=await asyncio.to_thread(infer)
            frame=BrowserFrame.model_validate({"hands":hands,"width":width,"height":height,
                "fps":header["fps"],"inference_ms":duration,"compute":header["compute"]})
            state=engine.publish_external(owner,frame.model_dump())
            await websocket.send_json(state)
    except (WebSocketDisconnect,asyncio.TimeoutError):pass
    except Exception as error:
        try:await websocket.send_json({"error":str(error)})
        except Exception:pass
        try:await websocket.close(code=1008)
        except Exception:pass
    finally:
        if detector is not None:await asyncio.to_thread(detector.close)
        engine.release_external(owner)


@app.get("/api/diagnostic/reference")
def diagnostic_reference():
    path=ROOT / "artifacts/mediapipe-right-hands.jpg"
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path)


@app.post("/api/diagnostic/gpu")
async def save_gpu_diagnostic(request:Request):
    gpu_diagnostic.clear()
    gpu_diagnostic.update(await request.json())
    return {"ok":True}


@app.get("/api/diagnostic/gpu")
def read_gpu_diagnostic():
    return gpu_diagnostic


app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")

