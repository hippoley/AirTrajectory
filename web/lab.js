const canvas=document.querySelector("#lab"),ctx=canvas.getContext("2d"),windEl=document.querySelector("#wind"),speedEl=document.querySelector("#speed");
const rooms=[{x:180,y:120,w:350,h:250,name:"LIVING"},{x:530,y:120,w:300,h:250,name:"BEDROOM"},{x:350,y:370,w:480,h:170,name:"STUDY"}],openings=[{id:"W1",x:180,y:210,side:"left",open:.65},{id:"W2",x:830,y:205,side:"right",open:.35},{id:"W3",x:720,y:540,side:"bottom",open:.55},{id:"D1",x:530,y:260,side:"internal",open:1},{id:"D2",x:440,y:370,side:"internal-horizontal",open:1}];
const fallback=[{name:"W1 · 25%",opens:[.25,.35,.55,1],co2:1045,series:[1260,1205,1162,1119,1081,1045],return:-8.2},{name:"W1 · 50%",opens:[.5,.35,.55,1],co2:925,series:[1260,1168,1090,1025,971,925],return:-7.1},{name:"W1 · 75%",opens:[.75,.35,.55,1],co2:842,series:[1260,1130,1030,952,891,842],return:-6.5},{name:"Cross-flow · W1 + W3",opens:[.55,.25,.85,1],co2:795,series:[1260,1108,1001,915,847,795],return:-6.1}];
let scenarios=fallback,baseline=1260,selected=0,cursor=0,timer=null,currentFrame=null,selectedOpening=null,objective="balanced",viewMode="flow",topologyRevision=0,trajectoryRevision=0,trajectoryStale=false;
async function loadScenarios(){const h=document.querySelector("#health");try{const r=await fetch("./data/scenarios.json",{cache:"no-store"});if(!r.ok)throw 0;const p=await r.json();if(!Array.isArray(p.scenarios)||p.scenarios.length<4)throw 0;scenarios=p.scenarios;baseline=p.baseline_co2;document.querySelector("#backendName").textContent=p.backend.toUpperCase();h.className="health ok";h.querySelector("b").textContent="BACKEND ARTIFACT READY"}catch(e){h.className="health fallback";h.querySelector("b").textContent="INTERACTIVE FALLBACK";document.querySelector("#backendName").textContent="FAST FALLBACK"}renderBranches();applyFrame(0,0);updateVector(scenarios[0])}
// Filament renderer: persistent pathlines, not decorative dots.
const PARTICLE_BUDGET=620;
const particles=Array.from({length:PARTICLE_BUDGET},(_,i)=>spawn(i));
function emissionWeight(o){
  const backend=currentFrame?.openings?.[o.id];
  const open=(backend!=null?backend/100:o.open);
  const v=backendVelocity(o.x+(o.side==="left"?18:o.side==="right"?-18:0),o.y+(o.side==="bottom"?-18:0));
  const speed=v?Math.hypot(v[0],v[1]):(+speedEl.value*.12);
  return Math.max(.01,open*open*(.35+speed));
}
function chooseInlet(){
  const inlet=openings.filter(o=>o.side!=="internal"&&o.side!=="internal-horizontal"&&o.open>.03);
  if(!inlet.length)return null;
  const weights=inlet.map(emissionWeight),total=weights.reduce((a,b)=>a+b,0);
  let pick=Math.random()*total;
  for(let i=0;i<inlet.length;i++){pick-=weights[i];if(pick<=0)return inlet[i]}
  return inlet[inlet.length-1];
}
function spawn(i){
  const source=chooseInlet();
  if(source){
    const jitter=(Math.random()-.5)*54;
    return{x:source.x+(source.side==="bottom"?jitter:(Math.random()*8-4)),y:source.y+(source.side==="bottom"?(Math.random()*8-4):jitter),life:Math.random()*90,maxLife:150+Math.random()*180,seed:Math.random()*99,px:0,py:0,trail:[]};
  }
  const r=rooms[i%rooms.length];
  return{x:r.x+12+Math.random()*(r.w-24),y:r.y+12+Math.random()*(r.h-24),life:0,maxLife:180+Math.random()*150,seed:Math.random()*99,px:0,py:0,trail:[]};
}
function inside(x,y){return rooms.find(r=>x>r.x&&x<r.x+r.w&&y>r.y&&y<r.y+r.h)}
function backendVelocity(x,y){
  const field=currentFrame?.field,vectors=field?.vectors,g=field?.grid;
  if(!vectors?.length)return null;
  if(g){
    const fx=Math.max(0,Math.min(g.nx-1,(x-g.x0)/g.dx)),fy=Math.max(0,Math.min(g.ny-1,(y-g.y0)/g.dy));
    const x0=Math.min(g.nx-2,Math.floor(fx)),y0=Math.min(g.ny-2,Math.floor(fy)),tx=fx-x0,ty=fy-y0;
    const at=(ix,iy)=>vectors[iy*g.nx+ix];
    const a=at(x0,y0),b=at(x0+1,y0),c=at(x0,y0+1),d=at(x0+1,y0+1);
    const lerp=(p,q,t)=>p+(q-p)*t;
    return[lerp(lerp(a[2],b[2],tx),lerp(c[2],d[2],tx),ty),lerp(lerp(a[3],b[3],tx),lerp(c[3],d[3],tx),ty)];
  }
  let nearest=[];
  for(const v of vectors){const dx=v[0]-x,dy=v[1]-y,d2=dx*dx+dy*dy;nearest.push([d2,v])}
  nearest.sort((a,b)=>a[0]-b[0]);nearest=nearest.slice(0,4);
  let sx=0,sy=0,sw=0;for(const [d2,v] of nearest){const w=1/Math.max(16,d2);sx+=v[2]*w;sy+=v[3]*w;sw+=w}
  return sw?[sx/sw,sy/sw]:null;
}
function wallResponse(x,y,vx,vy){
  const r=inside(x,y);if(!r)return[vx,vy];
  const dl=x-r.x,dr=r.x+r.w-x,dt=y-r.y,db=r.y+r.h-y,d=Math.min(dl,dr,dt,db);
  // No-slip-ish visual damping near walls; openings punch through this layer.
  let nearOpening=false;
  for(const o of openings){if(o.open>.05&&Math.hypot(o.x-x,o.y-y)<52){nearOpening=true;break}}
  if(!nearOpening&&d<34){
    const k=Math.max(.16,d/34);vx*=k;vy*=k;
    // Gentle tangential recirculation along solid boundaries.
    const swirl=(1-k)*.11;
    if(d===dl||d===dr)vy+=(d===dl?1:-1)*swirl;
    else vx+=(d===dt?-1:1)*swirl;
  }
  return[vx,vy];
}
function jetResponse(x,y,vx,vy){
  for(const o of openings){
    if(o.open<.05)continue;
    const dx=x-o.x,dy=y-o.y;
    const horizontal=o.side==="bottom"||o.side==="internal-horizontal";
    const axial=horizontal?Math.abs(dy):Math.abs(dx),lateral=horizontal?Math.abs(dx):Math.abs(dy);
    if(axial>145||lateral>58)continue;
    const core=Math.exp(-lateral*lateral/620)*Math.exp(-axial/115)*o.open;
    if(horizontal){
      const sign=o.side==="bottom"?-1:(y<o.y?-1:1);
      vy+=sign*core*.78;
      // Shear layer: slight outward spread after the jet core.
      vx+=Math.sign(dx||1)*core*(lateral/58)*.16;
    }else{
      const sign=o.side==="left"?1:o.side==="right"?-1:(x<o.x?-1:1);
      vx+=sign*core*.78;
      vy+=Math.sign(dy||1)*core*(lateral/58)*.16;
    }
  }
  return[vx,vy];
}
function velocity(x,y,p){
  const base=backendVelocity(x,y)||flowAt(x,y,p);
  let shaped=jetResponse(x,y,base[0],base[1]);
  shaped=wallResponse(x,y,shaped[0],shaped[1]);
  const mag=Math.hypot(shaped[0],shaped[1]);
  // Curl is visual microstructure only; transport direction comes from backend field.
  const t=performance.now()*.00018;
  const curlX=Math.sin(y*.010+t+p.seed*.025)*.045+Math.sin((x+y)*.004-t)*.02;
  const curlY=-Math.cos(x*.010-t+p.seed*.025)*.045+Math.cos((x-y)*.004+t)*.02;
  return[shaped[0]+curlX*(.22+mag*.06),shaped[1]+curlY*(.22+mag*.06)];
}
function crossesSolidWall(x0,y0,x1,y1){
  // Shared vertical wall: living <-> bedroom. Only D1 is permeable.
  if((x0<530&&x1>=530)||(x0>530&&x1<=530)){
    const t=(530-x0)/(x1-x0),y=y0+(y1-y0)*t;
    if(y>=120&&y<=370 && !(Math.abs(y-260)<=34 && openings.find(o=>o.id==="D1")?.open>.03))return true;
  }
  // Shared horizontal wall at y=370. D2 connects living <-> study only.
  if((y0<370&&y1>=370)||(y0>370&&y1<=370)){
    const t=(370-y0)/(y1-y0),x=x0+(x1-x0)*t;
    if(x>=350&&x<=830){
      const throughD2=x<=530&&Math.abs(x-440)<=34&&openings.find(o=>o.id==="D2")?.open>.03;
      if(!throughD2)return true;
    }
  }
  return false;
}
function advect(p,dt){
  // Midpoint/RK2 advection makes curved streamlines much less angular.
  const a=velocity(p.x,p.y,p),mx=p.x+a[0]*dt*.5,my=p.y+a[1]*dt*.5,b=velocity(mx,my,p);
  p.px=p.x;p.py=p.y;
  const nx=p.x+b[0]*dt,ny=p.y+b[1]*dt;
  if(crossesSolidWall(p.x,p.y,nx,ny)){
    // Preserve identity and slide along the wall instead of teleporting/resetting.
    const tryX=p.x+b[0]*dt,tryY=p.y+b[1]*dt;
    if(!crossesSolidWall(p.x,p.y,tryX,p.y)&&inside(tryX,p.y))p.x=tryX;
    else if(!crossesSolidWall(p.x,p.y,p.x,tryY)&&inside(p.x,tryY))p.y=tryY;
  }else{p.x=nx;p.y=ny}
  p.life++;
  const speed=Math.hypot(b[0],b[1]);
  // Fast coherent flow keeps a denser pathline; dead zones shed samples.
  const stride=speed>.55?1:speed>.24?2:4;
  if(p.life%stride===0)p.trail.push([p.x,p.y,speed]);
  if(p.trail.length>20)p.trail.shift();
  if(!inside(p.x,p.y)||p.life>p.maxLife)Object.assign(p,spawn(Math.floor(Math.random()*rooms.length)));
}
function flowAt(x,y,p){const a=(+windEl.value+180)*Math.PI/180,s=+speedEl.value;let vx=Math.cos(a)*(.25+s*.13),vy=Math.sin(a)*(.25+s*.13);for(const o of openings){const dx=o.x-x,dy=o.y-y,d2=dx*dx+dy*dy+4200,k=o.open*1850/d2;vx+=dx*k;vy+=dy*k}vx+=Math.sin(y*.018+p.seed)*.12;vy+=Math.cos(x*.017-p.seed)*.1;return[vx,vy]}function reset(p){Object.assign(p,spawn(Math.floor(Math.random()*rooms.length)))}
function reseedForField(){
  // Keep most trajectories continuous; only refresh a fraction so changed
  // opening states reshape density without a distracting full-screen reset.
  for(let i=0;i<particles.length;i+=5)reset(particles[i]);
}
function invalidateTrajectory(reason){
  topologyRevision++;trajectoryStale=true;stop();
  document.querySelector("#topologyRevision").textContent="TOPOLOGY r"+topologyRevision;
  document.querySelector("#health").className="health fallback";
  document.querySelector("#health").querySelector("b").textContent="TRAJECTORY STALE";
  document.querySelector("#scenario").textContent="TOPOLOGY MODIFIED";
  document.querySelector("#scenarioTitle").textContent=reason+" · re-run required";
  document.querySelector("#forkState").textContent="STALE · OLD FUTURES LOCKED";
  document.querySelector("#rerun").classList.remove("hidden");
}
function restoreBackendTrajectory(){
  trajectoryRevision=topologyRevision;trajectoryStale=false;
  document.querySelector("#health").className="health ok";
  document.querySelector("#health").querySelector("b").textContent="BACKEND ARTIFACT READY";
  document.querySelector("#forkState").textContent="BACKEND ORIGIN";
  document.querySelector("#rerun").classList.add("hidden");
  applyFrame(selected,0);
}
function openingFlow(o){return currentFrame?.field?.opening_flow_estimate?.[o.id]??null}
function renderInspector(){
  const box=document.querySelector("#openingRows");if(!box)return;
  const values=openings.map(o=>openingFlow(o)).filter(v=>v!=null),maxFlow=Math.max(.001,...values);
  box.innerHTML=openings.map(o=>{const f=openingFlow(o),relative=f==null?o.open:f/maxFlow,label=f==null?`${Math.round(o.open*100)}%`:`${f.toFixed(3)} q`;return `<div class="opening-row ${selectedOpening===o.id?"active":""}" data-opening="${o.id}"><b>${o.id}</b><div class="fluxbar"><i style="width:${Math.round(relative*100)}%"></i></div><strong>${label}</strong></div>`}).join("");
  box.querySelectorAll(".opening-row").forEach(row=>row.onclick=()=>selectOpening(row.dataset.opening));
}
function selectOpening(id){selectedOpening=id;document.querySelector("#selectedOpening").textContent=id+" · BACKEND FLOW";renderInspector()}
function cycleOpening(id){const o=openings.find(x=>x.id===id);if(!o)return;o.open=(((Math.round(o.open*4)+1)%5)/4);renderInspector();invalidateTrajectory(id+" → "+Math.round(o.open*100)+"%") }
function drawDeadZones(){if(viewMode!=="dead")return;for(const r of rooms){for(let y=r.y+24;y<r.y+r.h-16;y+=30)for(let x=r.x+24;x<r.x+r.w-16;x+=30){const q={seed:0},v=backendVelocity(x,y)||flowAt(x,y,q),s=Math.hypot(...v);if(s<.48){ctx.strokeStyle="rgba(132,91,91,.18)";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x-6,y+6);ctx.lineTo(x+6,y-6);ctx.stroke()}}}}
function drawPlan(){ctx.fillStyle="#080c0e";ctx.fillRect(0,0,1100,650);ctx.strokeStyle="#172126";ctx.lineWidth=1;for(let x=0;x<1100;x+=25){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,650);ctx.stroke()}for(let y=0;y<650;y+=25){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(1100,y);ctx.stroke()}for(const r of rooms){ctx.fillStyle="#0f1619";ctx.fillRect(r.x,r.y,r.w,r.h);ctx.strokeStyle="#6f8086";ctx.lineWidth=3;ctx.strokeRect(r.x,r.y,r.w,r.h);ctx.fillStyle="#728187";ctx.font="600 11px ui-monospace";ctx.fillText(r.name,r.x+14,r.y+22)}drawDeadZones();for(const o of openings){ctx.strokeStyle=o.open>.05?"#dce7e9":"#664f4f";ctx.lineWidth=8;ctx.beginPath();if(o.side==="bottom"||o.side==="internal-horizontal"){ctx.moveTo(o.x-32,o.y);ctx.lineTo(o.x+32,o.y)}else{ctx.moveTo(o.x,o.y-32);ctx.lineTo(o.x,o.y+32)}ctx.stroke();ctx.fillStyle="#9aa8ad";ctx.font="9px ui-monospace";ctx.fillText(o.id+" "+Math.round(o.open*100)+"%",o.x+9,o.y-38)}}
function drawCo2Overlay(){
  if(viewMode!=="co2"||!currentFrame?.co2)return;
  for(const r of rooms){const ppm=currentFrame.co2[r.name.toLowerCase()];if(ppm==null)continue;const severity=Math.max(0,Math.min(1,(ppm-600)/900));ctx.fillStyle=`rgba(176,112,78,${.05+severity*.22})`;ctx.fillRect(r.x+3,r.y+3,r.w-6,r.h-6);ctx.fillStyle="rgba(239,225,213,.86)";ctx.font="600 18px ui-monospace";ctx.fillText(Math.round(ppm)+" ppm",r.x+14,r.y+r.h-18)}
}
function drawFlowSkeleton(){
  const field=currentFrame?.field?.vectors;if(!field?.length)return;
  ctx.save();ctx.globalCompositeOperation="screen";ctx.lineCap="round";
  for(let i=0;i<field.length;i+=3){
    const v=field[i],speed=Math.hypot(v[2],v[3]);if(speed<.28)continue;
    const scale=Math.min(32,10+speed*18),mag=Math.max(.001,speed);
    const ex=v[0]+v[2]/mag*scale,ey=v[1]+v[3]/mag*scale;
    ctx.strokeStyle=`rgba(118,166,169,${Math.min(.12,(speed-.2)*.08)})`;
    ctx.lineWidth=.45;ctx.beginPath();ctx.moveTo(v[0],v[1]);ctx.lineTo(ex,ey);ctx.stroke();
  }
  ctx.restore();
}
function frame(){
  drawPlan();
  drawCo2Overlay();
  if(viewMode==="flow")drawFlowSkeleton();
  ctx.save();
  ctx.globalCompositeOperation="screen";
  ctx.lineCap="round";ctx.lineJoin="round";
  for(const p of particles){
    advect(p,1.55);
    if(viewMode!=="flow"||p.trail.length<3)continue;
    const speed=p.trail[p.trail.length-1][2];
    // Density + persistence encode magnitude: jets read as coherent bundles,
    // while dead zones become sparse, faint and short-lived.
    const alpha=Math.min(.34,.012+speed*.095);
    if(speed<.10 && ((p.seed*997+p.life)%3)>1)continue;
    for(let j=1;j<p.trail.length;j++){
      const age=j/p.trail.length,a=alpha*age*age;
      ctx.strokeStyle=`rgba(174,224,226,${a})`;
      ctx.lineWidth=.22+age*.52+Math.min(.42,speed*.10);
      ctx.beginPath();ctx.moveTo(p.trail[j-1][0],p.trail[j-1][1]);ctx.lineTo(p.trail[j][0],p.trail[j][1]);ctx.stroke();
    }
    // Tiny bright head, deliberately not a visible "dot".
    ctx.strokeStyle=`rgba(218,244,241,${Math.min(.42,alpha*1.35)})`;
    ctx.lineWidth=.55;ctx.beginPath();ctx.moveTo(p.px,p.py);ctx.lineTo(p.x,p.y);ctx.stroke();
  }
  ctx.restore();
  requestAnimationFrame(frame);
}
function ensureFrames(s){if(s.frames)return s.frames;return s.series.map((v,i)=>({step:i,co2:{living:v},openings:{W1:(s.opens[0]??0)*100,W2:(s.opens[1]??0)*100,W3:(s.opens[2]??0)*100,D1:(s.opens[3]??1)*100}}))}
function metrics(s){const d=Math.max(0,baseline-s.co2);return{coverage:Math.min(96,Math.round(60+d/15)),dead:Math.max(3,Math.round(24-d/22))}}function applyFrame(i,step){selected=i;const s=scenarios[i],frames=ensureFrames(s),k=Math.max(0,Math.min(step,frames.length-1)),fr=frames[k],living=fr.co2.living??s.series[k]??s.co2,m=metrics({...s,co2:living});cursor=k;currentFrame=fr;for(const o of openings){if(fr.openings&&fr.openings[o.id]!=null)o.open=fr.openings[o.id]/100}document.querySelector("#scenario").textContent="PLAYING COUNTERFACTUAL";document.querySelector("#scenarioTitle").textContent=s.name;document.querySelector("#co2").textContent=Math.round(living).toLocaleString();document.querySelector("#coverage").textContent=m.coverage;document.querySelector("#dead").textContent=m.dead;document.querySelector("#clock").textContent=`t+${String(k+1).padStart(2,"0")}`;document.querySelector("#frameCount").textContent=`${String(k+1).padStart(2,"0")} / ${frames.length}`;const scrub=document.querySelector("#scrubber");scrub.max=Math.max(0,frames.length-1);scrub.value=k;renderInspector();reseedForField();document.querySelectorAll(".branch").forEach((b,j)=>b.classList.toggle("active",i===j));document.querySelectorAll(".node").forEach((n,j)=>{n.classList.toggle("cursor",j===Math.floor(k/Math.max(1,frames.length-1)*8));n.classList.toggle("past",j<=Math.floor(k/Math.max(1,frames.length-1)*8))})}
function applyScenario(i){stop();applyFrame(i,ensureFrames(scenarios[i]).length-1);updateVector(scenarios[i])}
function stop(){if(timer){clearInterval(timer);timer=null}document.querySelector("#play").textContent="▶";document.querySelector("#timeline").classList.remove("playing")}
function play(){if(timer){stop();return}const frames=ensureFrames(scenarios[selected]);if(cursor>=frames.length-1)cursor=0;document.querySelector("#play").textContent="Ⅱ";document.querySelector("#timeline").classList.add("playing");timer=setInterval(()=>{applyFrame(selected,cursor);cursor++;if(cursor>=frames.length)stop()},180)}
function scoreVector(s){if(s.metrics)return{iaq:s.metrics.iaq,flow:s.metrics.flow,motion:s.metrics.motion,ret:s.metrics.return};const final=s.co2??baseline,iaq=Math.max(0,Math.min(100,Math.round(100-(final-420)/9))),flow=Math.round((s.opens??[]).slice(0,3).reduce((a,v)=>a+v,0)/3*100),motion=Math.max(0,100-Math.round((s.opens??[]).slice(0,3).reduce((a,v)=>a+Math.abs(v),0)/3*100));return{iaq,flow,motion,ret:s.return}}
function objectiveScore(s){const v=scoreVector(s);if(objective==="fresh")return v.iaq*.7+v.flow*.3;if(objective==="quiet")return v.iaq*.35+v.motion*.65;return v.iaq*.55+v.flow*.2+v.motion*.25}
function updateVector(s){const v=scoreVector(s);document.querySelector("#compareTitle").textContent=s.name+" · t+30";document.querySelector("#vector").innerHTML=`<span>IAQ <b>${v.iaq}</b></span><span>FLOW <b>${v.flow}</b></span><span>MOTION <b>${v.motion}</b></span><span>RETURN <b>${Number(v.ret).toFixed(2)}</b></span>`}
function spark(series){const min=Math.min(...series),max=Math.max(...series),span=Math.max(1,max-min);return series.map(v=>"▁▂▃▄▅▆▇█"[Math.min(7,Math.floor((v-min)/span*7))]).join("")}function renderBranches(){const best=scenarios.reduce((b,s,i,a)=>objectiveScore(s)>objectiveScore(a[b])?i:b,0);document.querySelector("#branches").innerHTML=scenarios.map((s,i)=>`<article class="branch ${i===best?"best":""}" data-i="${i}"><b>${s.name}</b><div class="outcome">${s.co2} ppm</div><span class="delta">↓ ${baseline-s.co2} ppm · t+30</span><div class="spark">${spark(s.series)}</div><small>return ${s.return}</small></article>`).join("");document.querySelectorAll(".branch").forEach(b=>b.onclick=()=>{const i=+b.dataset.i;applyScenario(i);updateVector(scenarios[i])})}
document.querySelector("#fork").onclick=()=>{if(trajectoryStale)return;renderBranches();stop();document.querySelector("#forkState").textContent="BACKEND ORIGIN";applyFrame(2,0)};document.querySelector("#strategy").onclick=()=>{if(trajectoryStale)return;renderBranches();const best=scenarios.reduce((b,s,i,a)=>objectiveScore(s)>objectiveScore(a[b])?i:b,0);stop();applyFrame(best,0);updateVector(scenarios[best]);play()};document.querySelector("#play").onclick=play;document.querySelector("#scrubber").oninput=e=>{stop();applyFrame(selected,+e.target.value)};windEl.oninput=()=>document.querySelector("#windLabel").textContent=`${windEl.value}°`;speedEl.oninput=()=>{document.querySelector("#speedLabel").textContent=`${(+speedEl.value).toFixed(1)} m/s`;renderInspector()};const tl=document.querySelector("#timeline");for(let i=0;i<9;i++){const n=document.createElement("div");n.className="node"+(i===5?" active":"");tl.append(n);if(i<8){const l=document.createElement("div");l.className="line";tl.append(l)}}loadScenarios();frame();
canvas.addEventListener("mousemove",e=>{const rect=canvas.getBoundingClientRect(),x=(e.clientX-rect.left)*canvas.width/rect.width,y=(e.clientY-rect.top)*canvas.height/rect.height,r=inside(x,y),p=document.querySelector("#probe");if(!r){p.classList.add("hidden");return}const key=r.name.toLowerCase(),co2=currentFrame?.co2?.[key],v=backendVelocity(x,y)||flowAt(x,y,{seed:0}),speed=Math.hypot(...v);p.classList.remove("hidden");p.style.left=Math.min(rect.width-155,e.clientX-rect.left+14)+"px";p.style.top=Math.max(55,e.clientY-rect.top-18)+"px";document.querySelector("#probeRoom").textContent=r.name;document.querySelector("#probeValue").textContent=(co2!=null?co2+" ppm · ":"")+speed.toFixed(2)+(currentFrame?.field?" backend field":" flow proxy")});canvas.addEventListener("mouseleave",()=>document.querySelector("#probe").classList.add("hidden"));renderInspector();
document.querySelectorAll(".preset").forEach(btn=>btn.onclick=()=>{objective=btn.dataset.preset;document.querySelectorAll(".preset").forEach(x=>x.classList.toggle("active",x===btn));renderBranches()});
canvas.addEventListener("click",e=>{const rect=canvas.getBoundingClientRect(),x=(e.clientX-rect.left)*canvas.width/rect.width,y=(e.clientY-rect.top)*canvas.height/rect.height;let hit=null,dist=Infinity;for(const o of openings){const d=Math.hypot(o.x-x,o.y-y);if(d<dist&&d<55){hit=o;dist=d}}if(hit){selectOpening(hit.id);cycleOpening(hit.id)}});
document.querySelectorAll(".view").forEach(btn=>btn.onclick=()=>{viewMode=btn.dataset.view;document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x===btn));const legend=document.querySelector("#viewLegend");legend.innerHTML=viewMode==="flow"?"<span>→ backend direction</span><span>· filament magnitude</span><span>∷ opening flow</span>":viewMode==="co2"?"<span>room fill · backend CO₂</span><span>timeline frame aware</span>":"<span>× low-flow cells</span><span>backend field threshold</span>"});

document.querySelector("#rerun").onclick=restoreBackendTrajectory;
