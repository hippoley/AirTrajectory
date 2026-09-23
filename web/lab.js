const canvas=document.querySelector("#lab"),ctx=canvas.getContext("2d");
const windEl=document.querySelector("#wind"),speedEl=document.querySelector("#speed");
const rooms=[{x:180,y:120,w:350,h:250,name:"LIVING"},{x:530,y:120,w:300,h:250,name:"BEDROOM"},{x:350,y:370,w:480,h:170,name:"STUDY"}];
const openings=[{id:"W1",x:180,y:210,side:"left",open:.65},{id:"W2",x:830,y:205,side:"right",open:.35},{id:"W3",x:720,y:540,side:"bottom",open:.55},{id:"D1",x:530,y:260,side:"internal",open:1}];
const scenarios=[
 {name:"W1 · 25%",opens:[.25,.35,.55,1],co2:1038,coverage:69,dead:18},
 {name:"W1 · 50%",opens:[.50,.35,.55,1],co2:914,coverage:76,dead:14},
 {name:"W1 · 75%",opens:[.75,.35,.55,1],co2:826,coverage:82,dead:10},
 {name:"Cross-flow · W1 + W3",opens:[.55,.25,.85,1],co2:778,coverage:89,dead:6}
];
let activeScenario=null;
const particles=Array.from({length:720},(_,i)=>spawn(i));
function spawn(i){const r=rooms[i%rooms.length];return{x:r.x+12+Math.random()*(r.w-24),y:r.y+12+Math.random()*(r.h-24),life:Math.random()*230,seed:Math.random()*99,px:0,py:0}}
function inside(x,y){return rooms.find(r=>x>r.x&&x<r.x+r.w&&y>r.y&&y<r.y+r.h)}
function flowAt(x,y,p){const a=(+windEl.value+180)*Math.PI/180,s=+speedEl.value;let vx=Math.cos(a)*(.25+s*.13),vy=Math.sin(a)*(.25+s*.13);for(const o of openings){const dx=o.x-x,dy=o.y-y,d2=dx*dx+dy*dy+4200,k=o.open*1850/d2;vx+=dx*k;vy+=dy*k}vx+=Math.sin(y*.018+p.seed)*.12;vy+=Math.cos(x*.017-p.seed)*.10;return[vx,vy]}
function reset(p){Object.assign(p,spawn(Math.floor(Math.random()*rooms.length)))}
function drawPlan(){ctx.fillStyle="#090d0f";ctx.fillRect(0,0,1100,650);ctx.strokeStyle="#182126";ctx.lineWidth=1;for(let x=0;x<1100;x+=25){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,650);ctx.stroke()}for(let y=0;y<650;y+=25){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(1100,y);ctx.stroke()}for(const r of rooms){ctx.fillStyle="#101619";ctx.fillRect(r.x,r.y,r.w,r.h);ctx.strokeStyle="#718087";ctx.lineWidth=3;ctx.strokeRect(r.x,r.y,r.w,r.h);ctx.fillStyle="#728087";ctx.font="600 11px ui-monospace";ctx.fillText(r.name,r.x+14,r.y+22)}for(const o of openings){ctx.strokeStyle=o.open>.05?"#dce7e9":"#664f4f";ctx.lineWidth=8;ctx.beginPath();if(o.side==="bottom"){ctx.moveTo(o.x-32,o.y);ctx.lineTo(o.x+32,o.y)}else{ctx.moveTo(o.x,o.y-32);ctx.lineTo(o.x,o.y+32)}ctx.stroke();ctx.fillStyle="#9aa8ad";ctx.font="9px ui-monospace";ctx.fillText(o.id,o.x+9,o.y-38)}}
function frame(){drawPlan();ctx.globalCompositeOperation="lighter";for(const p of particles){p.px=p.x;p.py=p.y;const[vx,vy]=flowAt(p.x,p.y,p),v=Math.hypot(vx,vy);p.x+=vx*2.1;p.y+=vy*2.1;p.life++;if(!inside(p.x,p.y)||p.life>280){reset(p);continue}ctx.strokeStyle=`rgba(160,220,230,${Math.min(.52,.09+v*.15)})`;ctx.lineWidth=.7+Math.min(1.2,v*.3);ctx.beginPath();ctx.moveTo(p.px,p.py);ctx.lineTo(p.x,p.y);ctx.stroke()}ctx.globalCompositeOperation="source-over";requestAnimationFrame(frame)}
function applyScenario(i){activeScenario=i;const s=scenarios[i];openings.forEach((o,j)=>o.open=s.opens[j]);document.querySelector("#scenario").textContent="COUNTERFACTUAL FUTURE";document.querySelector("#scenarioTitle").textContent=s.name;document.querySelector("#co2").textContent=s.co2.toLocaleString();document.querySelector("#coverage").textContent=s.coverage;document.querySelector("#dead").textContent=s.dead;document.querySelectorAll(".branch").forEach((b,j)=>b.classList.toggle("active",i===j))}
function renderBranches(){document.querySelector("#branches").innerHTML=scenarios.map((s,i)=>`<article class="branch" data-i="${i}"><b>${s.name}</b><div class="outcome">${s.co2} ppm</div><span class="delta">↓ ${1260-s.co2} ppm · t+30m</span><br>coverage ${s.coverage}% · dead zone ${s.dead}%</article>`).join("");document.querySelectorAll(".branch").forEach(b=>b.onclick=()=>applyScenario(+b.dataset.i))}
document.querySelector("#fork").onclick=()=>{renderBranches();applyScenario(2)};
document.querySelector("#strategy").onclick=()=>{renderBranches();applyScenario(3)};
windEl.oninput=()=>document.querySelector("#windLabel").textContent=`${windEl.value}°`;
speedEl.oninput=()=>document.querySelector("#speedLabel").textContent=`${(+speedEl.value).toFixed(1)} m/s`;
const tl=document.querySelector("#timeline");for(let i=0;i<9;i++){const n=document.createElement("div");n.className="node"+(i===5?" active":"");tl.append(n);if(i<8){const l=document.createElement("div");l.className="line";tl.append(l)}}frame();