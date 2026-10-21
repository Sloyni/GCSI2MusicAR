import json
import struct
from fastapi.testclient import TestClient
from musicar.server import app, engine
from musicar.gestures import Settings


def test_static_ui_and_assets_are_served():
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert "MusicAR" in client.get("/").text
        assert client.get("/static/app.js").status_code == 200
        health = client.get("/api/health").json()
        assert health["model_ready"] and health["samples_ready"]
        assert client.get("/assets/audio/C4.mp3").headers["content-type"] == "audio/mpeg"


def test_config_validation_and_cross_origin_protection():
    with TestClient(app) as client:
        engine.configure(Settings())
        valid = client.get("/api/config").json()["config"]
        assert client.put("/api/config",json={**valid,"octave":5}).status_code == 200
        assert client.put("/api/config",json={**valid,"height":.9}).status_code == 422
        assert client.post("/api/panic",headers={"Origin":"https://other.example"}).status_code == 403
        assert client.post("/api/panic",headers={"Origin":"http://testserver"}).status_code == 200
        assert client.get("/",headers={"host":"untrusted.example"}).status_code == 400
        engine.configure(Settings())


def test_websocket_binary_framing_and_ordered_note_delivery():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            packet = ws.receive_bytes()
            length = struct.unpack(">I",packet[:4])[0]
            metadata = json.loads(packet[4:4+length])
            assert metadata["status"] == "idle"
            assert "settings" in metadata
            with engine.lock:
                engine._events([{"kind":"on","note":60,"source":"test","velocity":.7},
                                {"kind":"off","note":60,"source":"test"}])
            packet = ws.receive_bytes()
            length = struct.unpack(">I",packet[:4])[0]
            events = json.loads(packet[4:4+length])["events"]
            assert [e["kind"] for e in events] == ["on","off"]
            assert events[0]["id"] < events[1]["id"]


def test_camera_error_is_actionable_and_async(monkeypatch):
    def fake_run():
        with engine.lock:
            engine.status="error"
            engine.message="Caméra indisponible"
    monkeypatch.setattr(engine,"_run",fake_run)
    with TestClient(app) as client:
        response = client.post("/api/camera/start",json={"index":0})
        assert response.status_code == 200
        engine.thread.join(timeout=1)
        assert client.get("/api/health").json()["camera"] == "error"


def browser_frame(x=.09,y=.65):
    return {"hands":[{"label":"Right","confidence":.9,"landmarks":[[x,y,0] for _ in range(21)]}],
            "width":960,"height":540,"fps":60,"inference_ms":5,"compute":"GPU test"}


def test_gpu_bridge_emits_contact_notes_on_the_first_frame_and_releases():
    with TestClient(app) as client:
        engine.configure(Settings(fingers=["index"]))
        with client.websocket_connect("/ws/hands") as ws:
            ws.send_json(browser_frame())
            result=ws.receive_json()
            assert result["compute"]=="GPU test" and result["events"][0]["kind"]=="on"
            assert result["events"][0]["note"]==60
            ws.send_json(browser_frame())
            assert ws.receive_json()["events"]==[]
            ws.send_json(browser_frame(y=.2))
            assert ws.receive_json()["events"][0]["kind"]=="off"
        assert engine.external_owner is None


def test_gpu_bridge_invalid_landmarks_are_rejected():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/hands") as ws:
            frame=browser_frame();frame["hands"][0]["landmarks"]=[]
            ws.send_json(frame)
            assert "error" in ws.receive_json()
        assert engine.external_owner is None

