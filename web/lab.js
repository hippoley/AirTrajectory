const canvas=document.querySelector("#lab");
const ctx=canvas.getContext("2d");
const windEl=document.querySelector("#wind");
const speedEl=document.querySelector("#speed");
const windLabel=document.querySelector("#windLabel");
const speedLabel=document.querySelector("#speedLabel");

const rooms=[
  {x:180,y:120,w:350,h:250,name:"LIVING",co2:1260},
  {x:530,y:120,w:300,h:250,name:"BEDROOM",co2:980},
  {x:350,y:370,w:480,h:170,name:"STUDY",co2:840}
];
const openings=[
  {x:180,y:210,side:"left",room:0,open:.65},
  {x:830,y:205,side:"right",room:1,open:.35},
  {x:720,y:540,side:"bottom",room:2,open:.55},
  {x:530,y:260,side:"internal",room:0,open:1}
];

const particles=Array.from({length:620},(_,i)=>spawn(i));
function spawn(i){
  const r=rooms[i%rooms.length];
  return {x:r.x+10+Math.random()*(r.w-20),y:r.y+10+Math.random()*(r.h-20),life:Math.random()*220,seed:Math.random()*99};
}
function inside(x,y){return rooms.find(r=>x>r.x&&x<r.x+r.w&&y>r.y&&y<r.y+r.h)}
function velocity(x,y,p){
  const angle=(Number(windEl.value)+180)*Math.PI/180;
  const base=Number(speedEl.value);
  const wave=Math.sin(y*.026+p.seed)*.34+Math.cos(x*.019-p.seed)*.22;
  let vx=Math.cos(angle)*(.42+base*.15)+wave;
  let vy=Math.sin(angle)*(.42+base*.15)+Math.sin(x*.015+p.seed)*.25;
  // pull flow toward openings to create visible source/path/sink structure
  for(const o of openings){
    const dx=o.x-x,dy=o.y-y,d2=dx*dx+dy*dy+5000;
    const k=o.open*1500/d2;
    vx+=dx*k;vy+=dy*k;
  }
  return [vx,vy];
}
function resetParticle(p){Object.assign(p,spawn(Math.floor(Math.random()*rooms.length)))}
function drawPlan(){
  ctx.fillStyle="#0b0f11";ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.strokeStyle="#1b2327";ctx.lineWidth=1;
  for(let x=0;x<canvas.width;x+=25){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,canvas.height);ctx.stroke()}
  for(let y=0;y<canvas.height;y+=25){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(canvas.width,y);ctx.stroke()}
  for(const r of rooms){
    ctx.fillStyle="#101619";ctx.fillRect(r.x,r.y,r.w,r.h);
    ctx.strokeStyle="#6f7d82";ctx.lineWidth=3;ctx.strokeRect(r.x,r.y,r.w,r.h);
    ctx.fillStyle="#68757a";ctx.font="600 11px ui-monospace";ctx.fillText(r.name,r.x+14,r.y+22);
  }
  for(const o of openings){
    ctx.strokeStyle=o.open>.05?"#dbe6e8":"#6b5555";ctx.lineWidth=8;ctx.beginPath();
    if(o.side==="left"||o.side==="right"||o.side==="internal"){ctx.moveTo(o.x,o.y-32);ctx.lineTo(o.x,o.y+32)}
    else{ctx.moveTo(o.x-32,o.y);ctx.lineTo(o.x+32,o.y)}
    ctx.stroke();
  }
}
function frame(){
  drawPlan();
  ctx.globalCompositeOperation="lighter";
  for(const p of particles){
    const [vx,vy]=velocity(p.x,p.y,p);
    const speed=Math.hypot(vx,vy);
    p.x+=vx*1.8;p.y+=vy*1.8;p.life++;
    if(!inside(p.x,p.y)||p.life>260)resetParticle(p);
    const a=Math.min(.55,.10+speed*.13);
    ctx.fillStyle=`rgba(167,220,229,${a})`;
    ctx.beginPath();ctx.arc(p.x,p.y,1.05+Math.min(1.5,speed*.35),0,Math.PI*2);ctx.fill();
  }
  ctx.globalCompositeOperation="source-over";
  requestAnimationFrame(frame);
}
windEl.addEventListener("input",()=>windLabel.textContent=`${windEl.value}°`);
speedEl.addEventListener("input",()=>speedLabel.textContent=`${Number(speedEl.value).toFixed(1)} m/s`);

const timeline=document.querySelector("#timeline");
for(let i=0;i<8;i++){const n=document.createElement("div");n.className="node"+(i===4?" active":"");timeline.append(n);if(i<7){const l=document.createElement("div");l.className="line";timeline.append(l)}}
function renderBranches(){
 const options=[["OPEN 25%","IAQ + / comfort ++"],["OPEN 50%","IAQ ++ / comfort +"],["OPEN 75%","IAQ +++ / draft +"],["W1 + W3","cross-flow candidate"]];
 document.querySelector("#branches").innerHTML=options.map(x=>`<div class="branch"><b>${x[0]}</b>${x[1]}</div>`).join("");
}
document.querySelector("#fork").onclick=renderBranches;
document.querySelector("#strategy").onclick=()=>{
 openings[0].open=.75;openings[1].open=.25;openings[2].open=.5;
 document.querySelector("#coverage").textContent="82";
 document.querySelector("#dead").textContent="9";
 renderBranches();
};
frame();