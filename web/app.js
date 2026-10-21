import {AudioEngine} from "/static/audio.js";
import {GpuCamera} from "/static/gpu-camera.js";
import {OPEN_STRINGS,previewGuitar,drawGuitar} from "/static/guitar.js";

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const canvas = $("#scene"), ctx = canvas.getContext("2d");
const audio = new AudioEngine(status => $("#audio-status").textContent = status === "Piano enregistré · prêt à jouer" && state.config?.instrument === "drums" ? "Percussions · prêtes à jouer" : status);
const state = { config:null, layout:null, hands:[], camera:"idle", bitmap:null, calibrating:false,guitar:null,gpuActive:false,
  pressed:new Map(), flashes:new Map(), ws:null, lastFrame:-1, recording:false, configured:false };
const names = ["Do","Do♯","Ré","Ré♯","Mi","Fa","Fa♯","Sol","Sol♯","La","La♯","Si"];
const whiteBindings = ["a","s","d","f","g","h","j","k","l"];
const blackBindings = ["w","e","t","y","u","o","p"];
let bindingMap = new Map(), configTimer, toastTimer, demoTimer, demoRunning=false, saveChain=Promise.resolve();
let playEpoch=0,noteSerial=0;
const latestPlay=new Map();
const gpu=new GpuCamera($("#gpu-video"),meta=>{updateCamera(meta);handleNotes(meta.events);},
  text=>{$("#compute-status").textContent=text;},error=>fallbackCpu(error));
let startingCamera=false,fallingBack=false;
let recording, recordingChunks=[], recordingUrl=null, recordStarted=0, recordClock;

function toast(message) {
  $("#toast").textContent = message;
  $("#toast").classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.remove("visible"), 4500);
}

async function api(path, method="GET", data) {
  const response = await fetch(path, {method, headers:{"Content-Type":"application/json"}, body:data === undefined ? undefined : JSON.stringify(data)});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail : "Réglage invalide ou service indisponible.");
  }
  return response.json();
}

function applySettings(result) {
  state.config = result.config;
  state.layout = result.layout;
  $("#mirror").checked = state.config.mirror;
  $("#octave").textContent = state.config.octave;
  $("#octave-down").disabled = state.config.octave <= 3 || state.config.instrument !== "piano";
  $("#octave-up").disabled = state.config.octave >= 5 || state.config.instrument !== "piano";
  $("#sensitivity").value = Math.round(state.config.sensitivity * 100);
  $("#sensitivity-value").textContent = `${Math.round(state.config.sensitivity * 100)} %`;
  $("#finger-count").textContent = `${state.config.fingers.length} doigt${state.config.fingers.length > 1 ? "s" : ""}`;
  $$("[data-finger]").forEach(button => {
    const selected = state.config.fingers.includes(button.dataset.finger);
    button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", selected);
  });
  $$("[data-instrument]").forEach(button => {
    const selected = state.config.instrument === button.dataset.instrument;
    button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", selected);
  });
  $("#sound-name").textContent = {piano:"Piano à queue",drums:"Batterie · synthèse",guitar:"Guitare acoustique"}[state.config.instrument];
  if(state.config.instrument==="guitar"&&audio.guitarBuffers.size===8)$("#audio-status").textContent="Guitare enregistrée · prête à jouer";
  else if(state.config.instrument==="drums"&&audio.context)$("#audio-status").textContent="Percussions · prêtes à jouer";
  else if(state.config.instrument==="piano"&&audio.buffers.size===17)$("#audio-status").textContent="Piano enregistré · prêt à jouer";
  else $("#audio-status").textContent="Cliquez pour activer le son";
  gpu.mirror=state.config.mirror;
  $("#gpu-video").style.transform=state.config.mirror?"scaleX(-1)":"none";
  $("#calibrate").disabled=state.config.instrument==="guitar";
  $("#gesture-tip").textContent={piano:"Un cercle de doigt sur une touche : la note joue. Sortez du clavier pour la couper.",drums:"Touchez un pad avec le cercle d’un doigt. Sortez puis revenez pour le rejouer.",guitar:"Montrez deux mains. La guitare suit vos paumes : une main sur le manche, l’autre sur les cordes."}[state.config.instrument];
  $("#try-piano").textContent="Ou jouez à la souris et au clavier";
  $("#keyboard-hint").textContent = state.config.instrument === "piano"
    ? "Touches blanches : A S D F G H J K L · touches noires : W E T Y U O P"
    : state.config.instrument==="guitar" ? "Cordes Mi La Ré Sol Si Mi · touches A S D F G H" : "Touches A S D F · kick, snare, hi-hat et tom";
  $("#keyboard-width").value = Math.round(state.config.width * 100);
  $("#keyboard-height").value = Math.round(state.config.height * 100);
  $("#keyboard-y").value = Math.round(state.config.y * 100);
  buildPlayable();
}

function saveConfig(patch, debounce=false) {
  if (!state.config) return;
  const desired = {...state.config, ...patch};
  // Clamp layout changes while preserving a useful visible surface.
  desired.x = Math.max(0, Math.min(desired.x, 1 - desired.width));
  desired.y = Math.max(.15, Math.min(desired.y, 1 - desired.height));
  state.config = desired;
  const send = () => {
    const snapshot = {...state.config};
    saveChain = saveChain.catch(() => {}).then(async () => {
      const result = await api("/api/config", "PUT", snapshot);
      applySettings(result);
      localStorage.setItem("musicar-config", JSON.stringify(result.config));
    }).catch(error => toast(error.message));
  };
  clearTimeout(configTimer);
  if (debounce) configTimer = setTimeout(send, 100); else send();
}

function buildPlayable() {
  const area = $("#playable");
  area.replaceChildren(); bindingMap.clear();
  if (state.config.instrument === "drums") {
    state.layout.pads.forEach((pad, i) => {
      const button = document.createElement("button");
      button.className = "drum-button"; button.dataset.note = pad.note;
      button.innerHTML = `<span>${pad.label}</span><kbd>${whiteBindings[i].toUpperCase()}</kbd>`;
      button.setAttribute("aria-label", pad.label);
      bindingMap.set(whiteBindings[i], pad.note); wirePointer(button, pad.note); area.append(button);
    });
  } else if(state.config.instrument==="guitar") {
    OPEN_STRINGS.forEach((note,i)=>{const button=document.createElement("button");button.className="guitar-string-button";button.dataset.note=note;
      const label=names[note%12]+(Math.floor(note/12)-1);button.innerHTML=`<span>${label}</span><kbd>${whiteBindings[i].toUpperCase()}</kbd>`;
      button.setAttribute("aria-label",`Corde ${i+1} · ${label}`);bindingMap.set(whiteBindings[i],note);wirePointer(button,note);area.append(button);});
  } else {
    let white=0, black=0;
    for (const key of state.layout.keys) {
      const button = document.createElement("button");
      button.className = `piano-key${key.black ? " black" : ""}`;
      button.dataset.note = key.note; button.setAttribute("aria-label", key.label);
      const binding = key.black ? blackBindings[black++] : whiteBindings[white++];
      if (key.black) {
        button.style.left = `${(key.x - state.config.x) / state.config.width * 100}%`;
        button.style.width = `${key.width / state.config.width * 100}%`;
      }
      const label = document.createElement("span"); label.className="note";
      label.textContent = key.black ? "" : key.label.replace(/\d/g, "");
      const hint = document.createElement("span"); hint.className="binding"; hint.textContent = binding?.toUpperCase() || "·";
      button.append(label,hint); if (binding) bindingMap.set(binding,key.note);
      wirePointer(button,key.note); area.append(button);
    }
  }
  updatePressed();
}

function wirePointer(button, note) {
  button.addEventListener("pointerdown", event => {
    event.preventDefault(); button.setPointerCapture(event.pointerId);
    play(note, `pointer:${event.pointerId}`, .72);
  });
  for (const type of ["pointerup","pointercancel","lostpointercapture"])
    button.addEventListener(type, event => release(`pointer:${event.pointerId}`));
  button.addEventListener("click", event => { if (event.detail === 0) { const source=`accessible:${note}`; play(note,source); setTimeout(()=>release(source),400); } });
}

async function play(note, source, velocity=.7) {
  const instrument=state.config.instrument;
  const epoch=playEpoch,serial=++noteSerial;latestPlay.set(source,serial);
  state.pressed.set(source,note);
  state.flashes.set(note,performance.now());
  const display = typeof note === "number" ? names[note%12]+(Math.floor(note/12)-1) : note.toUpperCase();
  $("#last-note").replaceChildren(document.createTextNode(display));
  const small=document.createElement("small");small.textContent="DERNIÈRE NOTE";$("#last-note").append(small);
  updatePressed();
  try {
    await audio.ensure(instrument);
    if(epoch!==playEpoch || latestPlay.get(source)!==serial) return;
    audio.noteOn(note,source,velocity,instrument);
    if (state.pressed.get(source) !== note) setTimeout(() => {if(latestPlay.get(source)===serial)audio.noteOff(source);}, 180);
  } catch(error) { release(source); toast(error.message); }
}

function release(source) {
  state.pressed.delete(source); audio.noteOff(source,source.startsWith("hand:")); updatePressed();
}

function updatePressed() {
  const notes = new Set(state.pressed.values());
  $$("[data-note]").forEach(button => button.classList.toggle("pressed", notes.has(isNaN(Number(button.dataset.note)) ? button.dataset.note : Number(button.dataset.note))));
}

function panic(notify=false) {
  playEpoch++;latestPlay.clear();
  clearTimeout(demoTimer); demoRunning=false; $("#demo").textContent="♫ Écouter un aperçu";
  state.pressed.clear(); audio.panic(); updatePressed();
  api("/api/panic","POST").catch(()=>{});
  if (notify) toast("Tous les sons ont été coupés.");
}

function toggleCalibration(value=!state.calibrating) {
  state.calibrating=value;
  $("#stage").classList.toggle("calibrating",value);
  $("#calibrate").classList.toggle("active",value);
  $("#calibration-banner").hidden=!value;
  $("#calibration-controls").hidden=!value;
  if(value) panic();
  $("#camera-empty").hidden=value || state.camera==="running";
}

function updateCamera(meta) {
  state.camera=meta.status; state.hands=meta.hands;state.guitar=meta.guitar||null;
  $("#studio-state").className=`studio-state ${meta.status}`;
  const labels={idle:"CAMÉRA EN VEILLE",starting:"CONNEXION…",running:"EN DIRECT",stopping:"FERMETURE…",error:"CAMÉRA INDISPONIBLE"};
  $("#state-label").textContent=labels[meta.status] || meta.status;
  $("#camera-empty").hidden=meta.status==="running" || state.calibrating;
  $("#start-camera").disabled=["starting","stopping"].includes(meta.status);
  $("#start-camera").innerHTML=`${meta.status==="starting" ? "Connexion…" : meta.status==="error" ? "Réessayer" : "Activer la caméra"} <svg><use href="#i-arrow"/></svg>`;
  $("#camera-message").textContent=["error","starting","stopping"].includes(meta.status) ? meta.message : "Activez la caméra et entrez dans le jeu.";
  $("#stop-camera").disabled=!["running","starting"].includes(meta.status);
  $("#camera-select").disabled=["running","starting","stopping"].includes(meta.status);
  $("#camera-dot").style.background=meta.status==="running" ? "#a6d8bd" : "#7d8484";
  $("#lens-label").textContent=meta.status==="running" ? "CAMÉRA · LOCAL" : "VUE AUGMENTÉE";
  $("#hand-status").innerHTML=`<svg><use href="#i-hand"/></svg> ${meta.hands.length} / 2 mains`;
  $("#fps").textContent=meta.status==="running" ? `${Math.round(meta.fps)} fps` : "— fps";
  $("#inference").textContent=meta.status==="running" ? `${Math.round(meta.inference_ms)} ms IA` : "— ms IA";
  $("#stage-instruction").textContent=state.config?.instrument==="guitar" ? (state.guitar?"TOUCHEZ LES CORDES. LA GUITARE SUIT VOS MAINS.":"MONTREZ DEUX MAINS ÉCARTÉES POUR CRÉER LA GUITARE.") : "ENTREZ SUR UNE NOTE. SORTEZ POUR LA COUPER.";
  if(meta.compute)$("#compute-status").textContent=meta.compute;
  if(meta.status!=="running" && state.bitmap){state.bitmap.close();state.bitmap=null;}
}

function handleNotes(events=[]){
  for(const note of events){if(note.kind==="off")release(`hand:${note.source}`);
    else if(!state.calibrating&&!document.hidden)play(note.note,`hand:${note.source}`,note.velocity);}
}

function connect() {
  const ws=new WebSocket(`${location.protocol==="https:" ? "wss" : "ws"}://${location.host}/ws`);
  state.ws=ws; ws.binaryType="arraybuffer";
  let decodedFrame=-1;
  ws.onmessage=async event=>{
    if(state.ws!==ws) return;
    const data=new Uint8Array(event.data), length=new DataView(event.data).getUint32(0);
    const meta=JSON.parse(new TextDecoder().decode(data.subarray(4,4+length)));
    if(meta.settings && state.configured) applySettings(meta.settings);
    if(state.gpuActive)return;
    updateCamera(meta);
    handleNotes(meta.events);
    if(data.length>length+4 && meta.frame_id!==decodedFrame) {
      decodedFrame=meta.frame_id;
      try {
        const bitmap=await createImageBitmap(new Blob([data.subarray(4+length)],{type:"image/jpeg"}));
        if(meta.frame_id<state.lastFrame || state.camera!=="running" || state.ws!==ws){bitmap.close();return;}
        state.bitmap?.close();state.bitmap=bitmap;state.lastFrame=meta.frame_id;
      } catch { /* one corrupt frame should not interrupt the instrument */ }
    }
  };
  ws.onclose=()=>{
    if(state.ws!==ws) return;
    panic();state.bitmap?.close();state.bitmap=null;state.hands=[];
    updateCamera({status:"error",hands:[],message:"Connexion au service interrompue. Reconnexion automatique…",fps:0,inference_ms:0});
    setTimeout(connect,1500);
  };
  ws.onerror=()=>ws.close();
}

function rounded(x,y,w,h,r=5) { ctx.beginPath();ctx.roundRect(x,y,w,h,r); }

function videoRect() {
  const width=canvas.width,height=canvas.height;
  const source=state.gpuActive?{width:gpu.video.videoWidth,height:gpu.video.videoHeight}:state.bitmap;
  if(!source?.width) return {x:0,y:0,width,height};
  const scale=Math.min(width/source.width,height/source.height);
  const w=source.width*scale,h=source.height*scale;
  return {x:(width-w)/2,y:(height-h)/2,width:w,height:h};
}

function render(time) {
  requestAnimationFrame(render);
  const view=videoRect(),w=view.width,h=view.height;
  if(state.gpuActive)ctx.clearRect(0,0,canvas.width,canvas.height);
  else{ctx.fillStyle="#101618";ctx.fillRect(0,0,canvas.width,canvas.height);}
  ctx.save();ctx.translate(view.x,view.y);
  ctx.clearRect(0,0,w,h);
  if(state.gpuActive&&gpu.video.videoWidth){
    // Video is composited directly by the browser; draw only the AR overlay.
  } else if(state.bitmap) {
    // Letterbox the video. Geometry remains in the actual image coordinates.
    ctx.drawImage(state.bitmap,0,0,w,h);
    ctx.fillStyle="#0c131c16";ctx.fillRect(0,0,w,h);
  } else {
    const gradient=ctx.createLinearGradient(0,0,w,h);gradient.addColorStop(0,"#23292b");gradient.addColorStop(.55,"#1b2326");gradient.addColorStop(1,"#28302e");ctx.fillStyle=gradient;ctx.fillRect(0,0,w,h);
    const glow=ctx.createRadialGradient(w*.72,h*.35,0,w*.7,h*.4,w*.6);glow.addColorStop(0,"#6b6a4530");glow.addColorStop(1,"#3b424100");ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
    ctx.strokeStyle="#8c9b8d0b";ctx.lineWidth=1;
    for(let x=-w;x<=w*2;x+=80){ctx.beginPath();ctx.moveTo(w*.5+(x-w*.5)*.25,h*.48);ctx.lineTo(x,h);ctx.stroke();}
    for(let y=h*.49;y<h;y+=Math.pow((y/h)*3,2)){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
  }
  if(!state.config || !state.layout) {ctx.restore();return;}
  const s=state.config;
  const active=new Set(state.pressed.values());
  const scale=w/960;
  if(s.instrument==="piano") {
    const x=s.x*w,y=s.y*h,kw=s.width*w,kh=s.height*h;
    ctx.shadowColor="#0008";ctx.shadowBlur=24*scale;ctx.shadowOffsetY=9*scale;
    ctx.fillStyle="#171c1fec";rounded(x-7*scale,y-14*scale,kw+14*scale,kh+24*scale,9*scale);ctx.fill();ctx.shadowBlur=0;ctx.shadowOffsetY=0;
    for(const key of state.layout.keys) {
      const kx=key.x*w,ky=key.y*h,kww=key.width*w,khh=key.height*h;
      const pressed=active.has(key.note), flash=time-(state.flashes.get(key.note)||-1000)<180;
      const grad=ctx.createLinearGradient(kx,ky,kx,ky+khh);
      if(key.black){grad.addColorStop(0,pressed||flash?"#916840":"#252c31ef");grad.addColorStop(1,pressed||flash?"#d29a64":"#10171bfd");}
      else{grad.addColorStop(0,pressed||flash?"#f1bc86ed":"#e2e5dfbc");grad.addColorStop(1,pressed||flash?"#ffdbb4f5":"#f4f4e8e8");}
      ctx.fillStyle=grad;ctx.strokeStyle=key.black?"#090e10":"#405052aa";ctx.lineWidth=1;
      if(key.black){ctx.shadowColor="#0006";ctx.shadowBlur=4*scale;ctx.shadowOffsetY=3*scale;}
      rounded(kx+1,ky,kww-2,khh,3*scale);ctx.fill();ctx.stroke();ctx.shadowBlur=0;ctx.shadowOffsetY=0;
      if($("#show-labels").checked){ctx.fillStyle=key.black?"#9ba5a8":"#56605bf0";ctx.font=`${(key.black?8:10)*scale}px Segoe UI`;ctx.textAlign="center";ctx.fillText(key.label,kx+kww/2,ky+khh-13*scale);}
      if(!key.black){ctx.fillStyle="#ffffff44";ctx.fillRect(kx+3,ky+khh-4,kww-6,2);}
    }
    ctx.fillStyle="#d8b18b";ctx.font=`${8*scale}px Segoe UI`;ctx.textAlign="left";ctx.fillText("M U S I C A R",x+6*scale,y-5*scale);
  } else if(s.instrument==="drums") {
    for(const pad of state.layout.pads){
      const x=pad.x*w,y=pad.y*h,rx=pad.radius*w,ry=pad.radius*h;
      const pressed=active.has(pad.note)||time-(state.flashes.get(pad.note)||-1000)<180;
      ctx.save();ctx.translate(x,y);ctx.scale(rx,ry);ctx.beginPath();ctx.arc(0,0,1,0,Math.PI*2);
      const grad=ctx.createRadialGradient(-.2,-.3,0,0,0,1);grad.addColorStop(0,pressed?"#e7a262ee":"#7b5c43c9");grad.addColorStop(1,pressed?"#b87842ee":"#262b2cea");ctx.fillStyle=grad;ctx.fill();ctx.lineWidth=2/rx;ctx.strokeStyle="#d9b184bb";ctx.stroke();ctx.beginPath();ctx.arc(0,0,.85,0,Math.PI*2);ctx.strokeStyle="#cfac7b55";ctx.stroke();ctx.restore();ctx.textAlign="center";ctx.fillStyle="#f2cda7";ctx.font=`600 ${13*scale}px Segoe UI`;ctx.fillText(pad.label,x,y+5*scale);
    }
  } else {
    if(state.guitar||state.camera!=="running")drawGuitar(ctx,state.guitar||previewGuitar(w,h),w,h,time,active,state.flashes,$("#show-labels").checked);
    else{ctx.fillStyle="#f1c795";ctx.font="14px Segoe UI";ctx.textAlign="center";ctx.fillText("Montrez deux mains écartées pour faire apparaître la guitare",w/2,h*.63);}
  }
  if($("#show-hands").checked) drawHands(w,h,scale);
  if(state.calibrating){ctx.setLineDash([5,5]);ctx.strokeStyle="#ffc687";ctx.lineWidth=2;ctx.strokeRect(s.x*w-6,s.y*h-16,s.width*w+12,s.height*h+26);ctx.setLineDash([]);}
  ctx.restore();
}

const connections=[[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[0,17],[17,18],[18,19],[19,20]];
const fingerTips={thumb:4,index:8,middle:12,ring:16,pinky:20};
function drawHands(w,h,scale) {
  for(const hand of state.hands){
    const color=hand.id%2?"#ecc598":"#99d9d1",points=hand.landmarks;
    ctx.strokeStyle=color+"88";ctx.lineWidth=1.5*scale;
    for(const [a,b] of connections){ctx.beginPath();ctx.moveTo(points[a][0]*w,points[a][1]*h);ctx.lineTo(points[b][0]*w,points[b][1]*h);ctx.stroke();}
    for(let i=0;i<points.length;i++){
      const finger=Object.keys(fingerTips).find(name=>fingerTips[name]===i),active=finger&&state.config.fingers.includes(finger);
      const x=points[i][0]*w,y=points[i][1]*h;
      ctx.beginPath();ctx.arc(x,y,(active?5:2)*scale,0,Math.PI*2);ctx.fillStyle=active?color:color+"bb";ctx.fill();
      if(active){ctx.beginPath();ctx.arc(x,y,10*scale,0,Math.PI*2);ctx.strokeStyle=color+"99";ctx.lineWidth=1*scale;ctx.stroke();}
    }
  }
}

let drag=null;
canvas.addEventListener("pointerdown",event=>{
  if(!state.calibrating)return;
  const rect=canvas.getBoundingClientRect(),view=videoRect();
  drag={x:(event.clientX-rect.left)*canvas.width/rect.width,y:(event.clientY-rect.top)*canvas.height/rect.height,
        width:view.width,height:view.height,startX:state.config.x,startY:state.config.y};canvas.setPointerCapture(event.pointerId);
});
canvas.addEventListener("pointermove",event=>{
  if(!drag)return;
  const rect=canvas.getBoundingClientRect();
  saveConfig({x:drag.startX+((event.clientX-rect.left)*canvas.width/rect.width-drag.x)/drag.width,
              y:drag.startY+((event.clientY-rect.top)*canvas.height/rect.height-drag.y)/drag.height},true);
});
for(const type of ["pointerup","pointercancel","lostpointercapture"])canvas.addEventListener(type,()=>{drag=null;});

async function fallbackCpu(error){
  if(fallingBack)return;fallingBack=true;gpu.stop();state.gpuActive=false;$("#turbo").checked=false;
  try{await api("/api/camera/stop","POST");await api("/api/camera/start","POST",{index:Number($("#camera-select").value)});
    toast("Turbo indisponible : caméra Python activée. "+error.message);}
  catch(failure){toast(failure.message);}finally{fallingBack=false;}
}
async function startCamera(){
  if(startingCamera)return;startingCamera=true;
  $("#start-camera").disabled=true;
  try {
    await audio.ensure(state.config.instrument);
    if($("#turbo").checked){state.gpuActive=true;updateCamera({status:"starting",hands:[],message:"Initialisation du suivi GPU…",fps:0,inference_ms:0});
      try{await gpu.start(Number($("#camera-select").value));}catch(error){await fallbackCpu(error);}}
    else await api("/api/camera/start","POST",{index:Number($("#camera-select").value)});
  }catch(error){toast(error.message);$("#start-camera").disabled=false;}
  finally{startingCamera=false;}
}
$("#start-camera").addEventListener("click",startCamera);
async function stopCamera(){panic();gpu.stop();state.gpuActive=false;await api("/api/camera/stop","POST");}
$("#stop-camera").addEventListener("click",()=>stopCamera().catch(error=>toast(error.message)));
$("#turbo").addEventListener("change",async()=>{if(state.camera==="running"){await stopCamera();await startCamera();}});
$("#try-piano").addEventListener("click",async()=>{try{await audio.ensure(state.config.instrument);$("#playable").scrollIntoView({behavior:"smooth",block:"center"});$("#playable button")?.focus();toast("Jouez avec la souris ou les touches affichées sous les notes.");}catch(error){toast(error.message);}});
$("#mirror").addEventListener("change",event=>{panic();saveConfig({mirror:event.target.checked});});
$$("[data-instrument]").forEach(button=>button.addEventListener("click",()=>{if(state.config.instrument===button.dataset.instrument)return;panic();sustain(false);toggleCalibration(false);saveConfig({instrument:button.dataset.instrument});audio.ensure(button.dataset.instrument).catch(error=>toast(error.message));}));
$$("[data-finger]").forEach(button=>button.addEventListener("click",()=>{
  const finger=button.dataset.finger;const current=state.config.fingers;
  const fingers=current.includes(finger)?current.filter(name=>name!==finger):[...current,finger];
  if(!fingers.length){toast("Gardez au moins un doigt actif.");return;}panic();saveConfig({fingers});
}));
$("#sensitivity").addEventListener("input",event=>{$("#sensitivity-value").textContent=event.target.value+" %";saveConfig({sensitivity:Number(event.target.value)/100},true);});
$("#calibrate").addEventListener("click",()=>toggleCalibration());$("#finish-calibration").addEventListener("click",()=>toggleCalibration(false));
$("#keyboard-width").addEventListener("input",event=>saveConfig({width:Number(event.target.value)/100},true));
$("#keyboard-height").addEventListener("input",event=>saveConfig({height:Number(event.target.value)/100},true));
$("#keyboard-y").addEventListener("input",event=>saveConfig({y:Number(event.target.value)/100},true));
$("#reset-layout").addEventListener("click",()=>saveConfig({x:.07,y:.58,width:.86,height:.34}));
$("#octave-down").addEventListener("click",()=>{panic();saveConfig({octave:Math.max(3,state.config.octave-1)});});
$("#octave-up").addEventListener("click",()=>{panic();saveConfig({octave:Math.min(5,state.config.octave+1)});});
$("#volume").addEventListener("input",event=>{audio.setVolume(Number(event.target.value)/100);$("#volume-value").textContent=event.target.value;});
$("#reverb").addEventListener("input",event=>audio.setReverb(Number(event.target.value)/100));
function sustain(value){audio.setSustain(value);$("#sustain").classList.toggle("active",value);$("#sustain").setAttribute("aria-pressed",value);}
$("#sustain").addEventListener("click",()=>sustain(!audio.sustain));
$("#panic").addEventListener("click",()=>panic(true));
$("#fullscreen").addEventListener("click",()=>{if(document.fullscreenElement)document.exitFullscreen();else $("#stage").requestFullscreen().catch(()=>toast("Le plein écran n’est pas disponible dans cette fenêtre."));});
for(const id of ["help-dialog","about-dialog"]){const dialog=$("#"+id);dialog.querySelectorAll(".dialog-close,.dialog-done").forEach(button=>button.addEventListener("click",()=>dialog.close()));dialog.addEventListener("click",event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});}
$("#help-top").addEventListener("click",()=>$("#help-dialog").showModal());$("#about").addEventListener("click",()=>$("#about-dialog").showModal());
const ignoreKeys=()=>["INPUT","SELECT","TEXTAREA"].includes(document.activeElement?.tagName)||!!document.querySelector("dialog[open]");
document.addEventListener("keydown",event=>{
  if(event.key==="Escape"){panic();return;}if(event.repeat||ignoreKeys())return;
  if(event.code==="Space"){event.preventDefault();sustain(true);return;}
  const note=bindingMap.get(event.key.toLowerCase());if(note!==undefined){event.preventDefault();play(note,`key:${event.key.toLowerCase()}`);}
});
document.addEventListener("keyup",event=>{if(event.code==="Space"){sustain(false);return;}release(`key:${event.key.toLowerCase()}`);});
window.addEventListener("blur",()=>{sustain(false);panic();});
document.addEventListener("visibilitychange",()=>{if(document.hidden){sustain(false);panic();}});

$("#demo").addEventListener("click",async()=>{
  if(demoRunning){panic();return;}
  try{await audio.ensure(state.config.instrument);}catch(error){toast(error.message);return;}
  demoRunning=true;$("#demo").textContent="■ Arrêter l’aperçu";
  const root=12*(state.config.octave+1),piano=[0,4,7,12,7,4,2,5,9,14,9,5,0,4,7,12];
  let i=0;
  const tick=()=>{
    if(!demoRunning)return;
    const note=state.config.instrument==="piano"?root+piano[i]:state.config.instrument==="guitar"?OPEN_STRINGS[i%6]:["kick","hat","snare","hat","kick","hat","tom","snare"][i%8];
    const source=`demo:${i}`;play(note,source,.55+(i%4)*.07);setTimeout(()=>release(source),300);
    i++;if(i<piano.length)demoTimer=setTimeout(tick,330);else{demoRunning=false;$("#demo").textContent="♫ Écouter un aperçu";}
  };tick();
});

$("#record").addEventListener("click",async()=>{
  if(state.recording){recording.stop();return;}
  try{
    await audio.ensure(state.config.instrument);
    if(!window.MediaRecorder)throw new Error("Enregistrement indisponible dans cette version du navigateur.");
    const mime=["audio/webm;codecs=opus","audio/webm"].find(type=>MediaRecorder.isTypeSupported(type));
    if(!mime)throw new Error("Format WebM non disponible. Essayez le mode navigateur.");
    recording=new MediaRecorder(audio.recordDestination.stream,{mimeType:mime});recordingChunks=[];
    recording.ondataavailable=event=>{if(event.data.size)recordingChunks.push(event.data);};
    recording.onstop=()=>{
      state.recording=false;clearInterval(recordClock);$("#record-indicator").classList.remove("recording");
      $("#record").innerHTML='<svg><use href="#i-record"/></svg> Enregistrer';
      if(recordingUrl)URL.revokeObjectURL(recordingUrl);
      recordingUrl=URL.createObjectURL(new Blob(recordingChunks,{type:mime}));
      $("#download-recording").disabled=false;$("#record-label").textContent="Votre session est prête à exporter.";toast("Enregistrement terminé. Exportez pour le conserver.");
    };
    recording.start(250);state.recording=true;recordStarted=Date.now();
    $("#record-indicator").classList.add("recording");$("#record").textContent="■ Terminer";
    $("#download-recording").disabled=true;
    const update=()=>{const seconds=Math.floor((Date.now()-recordStarted)/1000);$("#record-label").textContent=`Enregistrement · ${Math.floor(seconds/60).toString().padStart(2,"0")}:${(seconds%60).toString().padStart(2,"0")}`;};update();recordClock=setInterval(update,1000);
  }catch(error){toast(error.message);}
});
$("#download-recording").addEventListener("click",()=>{if(!recordingUrl)return;const link=document.createElement("a");link.href=recordingUrl;link.download=`MusicAR-${new Date().toISOString().slice(0,19).replaceAll(":","-")}.webm`;link.click();});

async function init(){
  try{
    const result=await api("/api/config");applySettings(result);
    let saved=null;
    try{saved=JSON.parse(localStorage.getItem("musicar-config")||"null");}catch{localStorage.removeItem("musicar-config");}
    if(saved){if(!localStorage.getItem("musicar-ui-v2")&&saved.height===.25&&saved.y===.65){saved.height=.34;saved.y=.58;}
      try{applySettings(await api("/api/config","PUT",saved));}catch{localStorage.removeItem("musicar-config");}}
    localStorage.setItem("musicar-ui-v2","1");
    state.configured=true;connect();
    const health=await api("/api/health");
    if(!health.model_ready||!health.samples_ready)toast("Installation incomplète : relancez Installer.ps1 pour le modèle et les sons.");
  }catch(error){toast("Service Python indisponible. Lancez l’application avec Demarrer.cmd.");}
}
requestAnimationFrame(render);init();
