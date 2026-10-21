export const OPEN_STRINGS=[40,45,50,55,59,64];
const LABELS=["Mi2","La2","Ré3","Sol3","Si3","Mi4"];

export function previewGuitar(w,h){
  const a=[.22,.51],b=[.73,.56],dx=(b[0]-a[0])*w,dy=(b[1]-a[1])*h;
  const length=Math.hypot(dx,dy),ux=dx/length,uy=dy/length,spread=h*.19;
  const point=(u,v)=>[(a[0]*w+u*length*ux-v*uy)/w,(a[1]*h+u*length*uy+v*ux)/h];
  return {neck:a,body:b,length,spread,width:w,height:h,
    strings:OPEN_STRINGS.map((note,i)=>({index:i,note,label:LABELS[i],fret:0,
      start:point(-.08,(i-2.5)*spread/5),end:point(1.22,(i-2.5)*spread/5)}))};
}

export function drawGuitar(ctx,guitar,w,h,time,active,flashes,labels){
  const a=[guitar.neck[0]*w,guitar.neck[1]*h],b=[guitar.body[0]*w,guitar.body[1]*h];
  const angle=Math.atan2(b[1]-a[1],b[0]-a[0]),length=Math.hypot(b[0]-a[0],b[1]-a[1]);
  const spread=guitar.spread*h/guitar.height,r=spread*.92;
  ctx.save();ctx.translate(b[0],b[1]);ctx.rotate(angle);
  ctx.shadowColor="#0008";ctx.shadowBlur=20;ctx.shadowOffsetY=8;
  const wood=ctx.createLinearGradient(-r,-r,r,r);wood.addColorStop(0,"#ad713ce6");wood.addColorStop(.5,"#e2ac6af2");wood.addColorStop(1,"#754527ef");
  ctx.beginPath();ctx.moveTo(-.93*r,-.4*r);
  ctx.bezierCurveTo(-1.25*r,-.82*r,-.66*r,-1.06*r,-.18*r,-.79*r);
  ctx.bezierCurveTo(.07*r,-.61*r,.12*r,-.59*r,.34*r,-.79*r);
  ctx.bezierCurveTo(.89*r,-1.12*r,1.3*r,-.65*r,1.33*r,0);
  ctx.bezierCurveTo(1.3*r,.65*r,.89*r,1.12*r,.34*r,.79*r);
  ctx.bezierCurveTo(.12*r,.59*r,.07*r,.61*r,-.18*r,.79*r);
  ctx.bezierCurveTo(-.66*r,1.06*r,-1.25*r,.82*r,-.93*r,.4*r);ctx.closePath();
  ctx.fillStyle=wood;ctx.fill();ctx.strokeStyle="#eac18da9";ctx.lineWidth=3;ctx.stroke();ctx.shadowBlur=0;ctx.shadowOffsetY=0;
  // Neck, headstock, frets, soundhole and bridge follow the same hand transform.
  ctx.fillStyle="#382b24f2";ctx.fillRect(-length,-spread*.58,length-r*.40,spread*1.16);
  ctx.strokeStyle="#ab8962b0";ctx.lineWidth=1;ctx.strokeRect(-length,-spread*.58,length-r*.40,spread*1.16);
  ctx.fillStyle="#845630ef";ctx.beginPath();ctx.roundRect(-length*1.19,-spread*.62,length*.19,spread*1.24,8);ctx.fill();
  ctx.strokeStyle="#c9bdabc9";ctx.lineWidth=3;
  for(let i=0;i<3;i++){for(const side of [-1,1]){const x=-length*1.16+i*length*.05,y=side*spread*.66;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x,y+side*8);ctx.stroke();}}
  for(let i=0;i<7;i++){const x=-length+(i*.11+.04)*length;ctx.strokeStyle="#b6ae9bbc";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,-spread*.55);ctx.lineTo(x,spread*.55);ctx.stroke();if(i===2||i===4){ctx.fillStyle="#d6c5b6";ctx.beginPath();ctx.arc(x-length*.04,0,3,0,Math.PI*2);ctx.fill();}}
  ctx.fillStyle="#29201beb";ctx.beginPath();ctx.arc(r*.10,0,r*.25,0,Math.PI*2);ctx.fill();ctx.strokeStyle="#f0d49caf";ctx.lineWidth=3;ctx.stroke();
  ctx.fillStyle="#4e3125";ctx.beginPath();ctx.roundRect(length*.17,-spread*.64,Math.max(10,r*.13),spread*1.28,3);ctx.fill();
  ctx.restore();
  for(const string of guitar.strings){
    const x1=string.start[0]*w,y1=string.start[1]*h,x2=string.end[0]*w,y2=string.end[1]*h;
    const flash=time-(flashes.get(string.note)||-1000)<280,pressed=active.has(string.note),lit=flash||pressed;
    const vibration=flash?Math.sin(time*.07+string.index)*3:0;
    ctx.beginPath();ctx.moveTo(x1,y1);ctx.quadraticCurveTo((x1+x2)/2-Math.sin(angle)*vibration,(y1+y2)/2+Math.cos(angle)*vibration,x2,y2);
    ctx.strokeStyle=lit?"#fff1c4":"#d7c6a3e0";ctx.lineWidth=(6-string.index)*.22+.6;
    if(lit){ctx.shadowColor="#ffce87";ctx.shadowBlur=9;}ctx.stroke();ctx.shadowBlur=0;
    if(labels){ctx.font="10px Segoe UI";ctx.fillStyle="#ffdda9";ctx.textAlign="left";ctx.fillText(string.label+(string.fret?` · f${string.fret}`:""),x2+8,y2+3);}
  }
  for(const [point,label] of [[a,"MANCHE"],[b,"CORDES"]]){ctx.strokeStyle="#f2c99990";ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(point[0],point[1],12,0,Math.PI*2);ctx.stroke();ctx.font="8px Segoe UI";ctx.fillStyle="#f2c999";ctx.textAlign="center";ctx.fillText(label,point[0],point[1]-r*.9);}
}
