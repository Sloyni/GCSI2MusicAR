"""Short hardware/model check. No pictures are stored."""
import argparse
import json
from pathlib import Path
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--camera",type=int,default=0)
    parser.add_argument("--frames",type=int,default=30)
    parser.add_argument("--image",type=Path,help="Image de référence pour vérifier le modèle sans caméra")
    args=parser.parse_args()
    model=ROOT / "assets/models/hand_landmarker.task"
    detector=vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model)),
        running_mode=vision.RunningMode.VIDEO,num_hands=2))
    if args.image:
        try:
            image=mp.Image.create_from_file(str(args.image))
            result=detector.detect_for_video(image,1)
            print(json.dumps({"image":args.image.name,"hands":len(result.hand_landmarks),
                              "landmarks_per_hand":[len(hand) for hand in result.hand_landmarks],"model":"ok"},indent=2))
            if not result.hand_landmarks:raise RuntimeError("Aucune main détectée dans l'image de référence")
        finally:detector.close()
        return
    if args.frames<1:raise ValueError("--frames doit être positif")
    cap=cv2.VideoCapture(args.camera,cv2.CAP_DSHOW if __import__("sys").platform=="win32" else cv2.CAP_ANY)
    timings=[];hands=0;dimensions=None
    try:
        if not cap.isOpened():raise RuntimeError("Caméra non accessible")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,960);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,540)
        for i in range(args.frames):
            ok,frame=cap.read()
            if not ok:raise RuntimeError("Lecture caméra impossible")
            dimensions=[int(frame.shape[1]),int(frame.shape[0])]
            start=time.monotonic()
            result=detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(cv2.flip(frame,1),cv2.COLOR_BGR2RGB)),int(start*1000))
            timings.append((time.monotonic()-start)*1000)
            hands=max(hands,len(result.hand_landmarks))
        print(json.dumps({"camera":args.camera,"dimensions":dimensions,"frames":len(timings),
                          "inference_ms_mean":round(sum(timings)/len(timings),2),"max_hands_seen":hands,
                          "model":"ok","opencv":cv2.__version__,"mediapipe":mp.__version__},indent=2))
    finally:
        cap.release();detector.close()


if __name__=="__main__":main()
