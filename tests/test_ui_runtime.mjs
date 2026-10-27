import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {pathToFileURL} from "node:url";
import {resolve} from "node:path";

// A DOM model exercises our module without controlling the user's browser.
const nodes=new Map(),frames=[],calls=[];
class Element {
  constructor(id=""){this.id=id;this.children=[];this.dataset={};this.style={};this.checked=true;this.value="70";this.listeners=new Map();this.classList={add(){},remove(){},toggle(){}};}
  addEventListener(name,fn){this.listeners.set(name,fn);}
  setAttribute(){} append(...items){this.children.push(...items);} replaceChildren(...items){this.children=[...items];}
  querySelectorAll(){return [];} getBoundingClientRect(){return {left:0,top:0,width:960,height:540};}
}
const context=new Proxy({}, {get(target,key){
  if(key==="createLinearGradient"||key==="createRadialGradient")return ()=>({addColorStop(){}});
  if(!(key in target))target[key]=(...args)=>calls.push({key,args});
  return target[key];
}});
const node=id=>{if(!nodes.has(id))nodes.set(id,new Element(id));return nodes.get(id);};
node("#scene").getContext=()=>context;node("#scene").width=960;node("#scene").height=540;
globalThis.document={hidden:false,activeElement:null,querySelector(selector){return selector==="dialog[open]"?null:node(selector);},
  querySelectorAll(selector){return selector==="[data-note]"?node("#playable").children:[];},createElement:()=>new Element(),createTextNode:text=>text,addEventListener(){}};
globalThis.window={addEventListener(){}};
globalThis.location={protocol:"http:",host:"127.0.0.1:8765"};
globalThis.localStorage={getItem(){return null;},setItem(){},removeItem(){}};
globalThis.requestAnimationFrame=callback=>frames.push(callback);
globalThis.WebSocket=class{constructor(){globalThis.testSocket=this;} static OPEN=1;};
const realFetch=globalThis.fetch;
globalThis.fetch=async(url,options)=>{
  const response=await realFetch(url.startsWith("/")?"http://127.0.0.1:8765"+url:url,options);
  // A player may have selected another instrument in the live app. Keep our
  // initial fixture deterministic without changing their server settings.
  if(url==="/api/config"&&!options?.method||url==="/api/config"&&options?.method==="GET"){
    const body=await response.json();body.config.instrument="piano";
    return new Response(JSON.stringify(body),{status:200,headers:{"Content-Type":"application/json"}});
  }
  return response;
};
const code=(await readFile("web/app.js","utf8")).replaceAll(/from "\/static\/([^\"]+)"/g,(_,file)=>`from "${pathToFileURL(resolve("web",file)).href}"`);
await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
for(let i=0;i<100&&!globalThis.testSocket;i++)await new Promise(resolve=>setTimeout(resolve,10));
assert(globalThis.testSocket,"L'interface doit se connecter au service");
assert.equal(node("#playable").children.length,25,"Le piano doit construire 25 touches");
frames.shift()(100);
assert(calls.some(call=>call.key==="roundRect"),"Le clavier doit être dessiné");
const settings=await (await realFetch("http://127.0.0.1:8765/api/config")).json();
const packet={status:"idle",message:"test",hands:[],events:[],frame_id:1,event_id:0,revision:2,fps:0,inference_ms:0,
  settings:{...settings,config:{...settings.config,instrument:"guitar",guitar_mode:"chords"}}};
const metadata=new TextEncoder().encode(JSON.stringify(packet)),bytes=new Uint8Array(4+metadata.length);
new DataView(bytes.buffer).setUint32(0,metadata.length);bytes.set(metadata,4);
await testSocket.onmessage({data:bytes.buffer});
assert.equal(node("#playable").children.length,6,"La guitare doit construire six cordes jouables");
frames.shift()(200);
assert(calls.some(call=>call.key==="bezierCurveTo"),"La guitare doit dessiner sa caisse et son manche");
async function sendSettings(patch,extra={}){
  packet.settings.config={...packet.settings.config,...patch};Object.assign(packet,extra);
  const meta=new TextEncoder().encode(JSON.stringify(packet)),bytes=new Uint8Array(4+meta.length);
  new DataView(bytes.buffer).setUint32(0,meta.length);bytes.set(meta,4);
  await testSocket.onmessage({data:bytes.buffer});
}
await sendSettings({guitar_mode:"melody",music_style:"jazz"},{guitar:{melody:[48,50,52,55]}});
assert.equal(node("#playable").children.length,4,"Le mode mélodie doit exposer quatre pincements");
assert(node("#sound-name").textContent.includes("Jazz"),"Le style doit se refléter dans le son affiché");
await sendSettings({guitar_mode:"strings"},{guitar:null});
assert.equal(node("#playable").children.length,6,"Le mode cordes libres reste disponible");
const left={id:101,landmarks:Array.from({length:21},()=>[.2,.3,0])};
const right={id:102,landmarks:Array.from({length:21},()=>[.8,.3,0])};
await sendSettings({guitar_mode:"chords"},{hands:[left,right],guitar:null});
calls.length=0;frames.shift()(250);
const fingertipCircles=calls.filter(call=>call.key==="arc"&&[5,10].includes(call.args[2]));
assert(fingertipCircles.length>0,"La main droite conserve ses repères de contact");
assert(fingertipCircles.every(call=>call.args[0]===.8*960),"Aucun cercle de doigt ne doit être dessiné sur la main gauche");
await sendSettings({}, {hands:[]});
packet.settings.config.instrument="drums";
const drumMeta=new TextEncoder().encode(JSON.stringify(packet)),drumBytes=new Uint8Array(4+drumMeta.length);
new DataView(drumBytes.buffer).setUint32(0,drumMeta.length);drumBytes.set(drumMeta,4);
await testSocket.onmessage({data:drumBytes.buffer});frames.shift()(300);
assert.equal(node("#playable").children.length,6,"La batterie doit créer six pads");
assert(node("#guitar-mode-field").hidden,"Les modes guitare doivent se masquer pour la batterie");
assert(node("#pitch-gesture").disabled,"Le pitch continu est réservé aux instruments mélodiques");
console.log("Interface : piano, six accords, quatre pincements, six cordes, six pads et styles vérifiés.");
