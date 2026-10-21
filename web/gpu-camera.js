export class GpuCamera {
  constructor(video,onResult,onStatus,onFailure){
    this.video=video;this.onResult=onResult;this.onStatus=onStatus;this.onFailure=onFailure;
    this.active=false;this.busy=false;this.awaiting=false;this.fps=0;
    this.delegate="HYBRID";
  }

  async start(index=0){
    if(!navigator.mediaDevices?.getUserMedia)throw new Error("Caméra web indisponible dans ce moteur.");
    this.active=true;
    this.worker=new Worker("/static/hand-worker.js");
    const ready=new Promise((resolve,reject)=>{
      const timeout=setTimeout(()=>reject(new Error("Initialisation GPU trop longue.")),30000);
      this.worker.onerror=event=>{clearTimeout(timeout);reject(new Error(event.message||"Le worker GPU a échoué."));};
      this.worker.onmessage=event=>{
        if(event.data.kind==="ready"){clearTimeout(timeout);this.info=event.data;resolve();}
        else if(event.data.kind==="error"){clearTimeout(timeout);reject(new Error(event.data.message));}
      };
    });
    this.worker.postMessage({kind:"init",delegate:this.delegate});
    // Load the model before asking for a camera, so GPU failures do not leave a
    // capture running. Permissions, when necessary, are handled by the user.
    await ready;
    let device;
    if(index>0){const devices=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==="videoinput");device=devices[index]?.deviceId;if(!device)throw new Error("Cette source caméra n’existe pas.");}
    this.stream=await navigator.mediaDevices.getUserMedia({video:{deviceId:device?{exact:device}:undefined,
      width:{ideal:960},height:{ideal:540},frameRate:{ideal:60,max:60}},audio:false});
    this.video.srcObject=this.stream;
    await this.video.play();
    this.video.hidden=false;
    const trackSettings=this.stream.getVideoTracks()[0].getSettings();
    this.onStatus(`CPU + GPU · ${this.info.renderer} · caméra ${trackSettings.frameRate||"?"} fps`);
    this.socket=new WebSocket(`${location.protocol==="https:"?"wss":"ws"}://${location.host}${this.delegate==="HYBRID"?"/ws/infer":"/ws/hands"}`);
    await new Promise((resolve,reject)=>{this.socket.onopen=resolve;this.socket.onerror=()=>reject(new Error("Service de gestes indisponible."));});
    this.socket.onmessage=event=>{
      this.awaiting=false;
      const result=JSON.parse(event.data);
      if(result.error){this.onFailure(new Error(result.error));return;}
      this.onResult(result);
      // Continue from the newest already-delivered camera frame immediately.
      // Waiting for the next camera callback here would halve throughput when
      // inference is just slower than the camera's frame interval.
      this.captureLatest?.();
    };
    this.socket.onclose=()=>{if(this.active)this.onFailure(new Error("Connexion du suivi GPU interrompue."));};
    this.worker.onmessage=event=>{
      if(!this.active)return;
      if(event.data.kind==="error"){this.onFailure(new Error(event.data.message));return;}
      if(!["result","encoded"].includes(event.data.kind))return;
      this.busy=false;
      const now=performance.now();
      if(this.lastResult)this.fps=this.fps*.8+Math.min(200,1000/(now-this.lastResult))*.2;
      this.lastResult=now;
      if(this.socket.readyState!==WebSocket.OPEN||this.awaiting)return;
      this.awaiting=true;
      if(event.data.kind==="encoded"){
        const header=new TextEncoder().encode(JSON.stringify({width:this.video.videoWidth,height:this.video.videoHeight,
          fps:this.fps,compute:`CPU XNNPACK + vidéo GPU · ${this.info.renderer}`}));
        const packet=new Uint8Array(4+header.length+event.data.bytes.byteLength);
        new DataView(packet.buffer).setUint32(0,header.length);packet.set(header,4);packet.set(new Uint8Array(event.data.bytes),4+header.length);
        this.socket.send(packet);return;
      }
      const hands=event.data.hands.map(hand=>({...hand,landmarks:hand.landmarks.map(([x,y,z])=>[this.mirror?1-x:x,y,z])}));
      this.socket.send(JSON.stringify({hands,width:this.video.videoWidth,height:this.video.videoHeight,
        fps:this.fps,inference_ms:event.data.inference_ms,compute:`GPU · ${this.info.renderer}`}));
    };
    this.lastVideoTime=-1;
    this.captureLatest=async()=>{
      if(!this.active)return;
      if(!this.busy&&!this.awaiting&&this.video.readyState>=2&&this.video.currentTime!==this.lastVideoTime){
        this.busy=true;this.lastVideoTime=this.video.currentTime;
        try{
          const bitmap=await createImageBitmap(this.video);
          if(!this.active){bitmap.close();return;}
          this.worker.postMessage({kind:"frame",bitmap,timestamp:performance.now()},[bitmap]);
        }catch(error){this.busy=false;this.onFailure(error);return;}
      }
    };
    const pump=()=>{
      if(!this.active)return;
      this.captureLatest();
      if(this.video.requestVideoFrameCallback)this.callback=this.video.requestVideoFrameCallback(pump);
      else this.callback=requestAnimationFrame(pump);
    };
    pump();
  }

  stop(){
    this.active=false;this.worker?.terminate();this.socket?.close();
    this.stream?.getTracks().forEach(track=>track.stop());
    this.video.srcObject=null;this.video.hidden=true;
    if(this.video.cancelVideoFrameCallback)this.video.cancelVideoFrameCallback(this.callback);
    else cancelAnimationFrame(this.callback);
    this.busy=false;this.awaiting=false;this.lastResult=null;this.fps=0;
  }
}
