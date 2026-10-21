// Classic worker: MediaPipe's WASM loader needs importScripts().
let detector,info,encodeCanvas;
self.onmessage=async event=>{
  const message=event.data;
  if(message.kind==="init") {
    try {
      const canvas=new OffscreenCanvas(256,256);
      const gl=canvas.getContext("webgl2",{powerPreference:"high-performance",antialias:false});
      if(!gl)throw new Error("WebGL2 indisponible");
      const extension=gl.getExtension("WEBGL_debug_renderer_info");
      const renderer=extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
      const delegate=message.delegate||"GPU";
      if(delegate==="HYBRID"){
        info={delegate,renderer};encodeCanvas=new OffscreenCanvas(640,360);
        self.postMessage({kind:"ready",...info});return;
      }
      const {FilesetResolver,HandLandmarker}=await import("/static/vendor/vision_bundle.mjs");
      const files=await FilesetResolver.forVisionTasks("/static/vendor/wasm");
      detector=await HandLandmarker.createFromOptions(files,{
        baseOptions:{modelAssetPath:"/assets/models/hand_landmarker.task",delegate},
        runningMode:"VIDEO",numHands:2,minHandDetectionConfidence:.5,
        minHandPresenceConfidence:.5,minTrackingConfidence:.5,canvas});
      info={delegate,renderer};
      self.postMessage({kind:"ready",...info});
    }catch(error){self.postMessage({kind:"error",message:error.message});}
  } else if(message.kind==="frame") {
    try {
      if(info.delegate==="HYBRID"){
        const width=Math.min(640,message.bitmap.width),height=Math.round(message.bitmap.height*width/message.bitmap.width);
        if(encodeCanvas.width!==width)encodeCanvas.width=width;
        if(encodeCanvas.height!==height)encodeCanvas.height=height;
        encodeCanvas.getContext("2d",{alpha:false}).drawImage(message.bitmap,0,0,width,height);
        const blob=await encodeCanvas.convertToBlob({type:"image/jpeg",quality:.76});
        const bytes=await blob.arrayBuffer();
        self.postMessage({kind:"encoded",bytes,...info},[bytes]);return;
      }
      const start=performance.now();
      const result=detector.detectForVideo(message.bitmap,message.timestamp);
      const inference_ms=performance.now()-start;
      const hands=result.landmarks.map((points,i)=>({label:result.handedness[i][0].categoryName,
        confidence:result.handedness[i][0].score,landmarks:points.map(p=>[p.x,p.y,p.z])}));
      self.postMessage({kind:"result",hands,inference_ms,...info});
    }catch(error){self.postMessage({kind:"error",message:error.message});}
    finally{message.bitmap.close();}
  }
};
