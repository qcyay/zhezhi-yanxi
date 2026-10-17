(() => {
 const canvas=document.getElementById('ambient-canvas'),ctx=canvas.getContext('2d'),reduced=matchMedia('(prefers-reduced-motion: reduce)');
 let width=0,height=0,t=0,raf=0,last=0;
 function draw(){
  ctx.clearRect(0,0,width,height);const mobile=width<800,cx=width*(mobile?.91:.81),cy=mobile?110:Math.min(145,height*.27),r=Math.min(width*(mobile?.27:.14),mobile?150:160);
  const glow=ctx.createRadialGradient(cx,cy,r*.12,cx,cy,r*1.45);glow.addColorStop(0,'#c5d7f45c');glow.addColorStop(.55,'#cfddf640');glow.addColorStop(1,'#cfddf600');ctx.fillStyle=glow;ctx.fillRect(0,0,width,height);
  const angle=t*.12,tilt=-.3;
  function project(x,y,z){const xx=x*Math.cos(angle)+z*Math.sin(angle),zz=-x*Math.sin(angle)+z*Math.cos(angle),yy=y*Math.cos(tilt)-zz*Math.sin(tilt),depth=y*Math.sin(tilt)+zz*Math.cos(tilt);return {x:cx+xx*r,y:cy+yy*r,z:depth}}
  function line(points,alpha){ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.strokeStyle=`rgba(71,112,174,${alpha})`;ctx.lineWidth=.8;ctx.stroke()}
  for(let lat=1;lat<21;lat++){const phi=lat*Math.PI/21,points=[];for(let j=0;j<=100;j++){const a=j*Math.PI*2/100;const ripple=1+.035*Math.sin(a*3+t*.6+phi*4);points.push(project(Math.sin(phi)*Math.cos(a)*ripple,Math.cos(phi),Math.sin(phi)*Math.sin(a)*ripple))}line(points,.18)}
  for(let lon=0;lon<25;lon++){const a=lon*Math.PI*2/25,points=[];for(let j=0;j<=70;j++){const phi=j*Math.PI/70;points.push(project(Math.sin(phi)*Math.cos(a),Math.cos(phi),Math.sin(phi)*Math.sin(a)))}line(points,.13)}
  // Separate orbital ribbons add depth without obscuring the portal text.
  for(let ring=0;ring<3;ring++){const points=[];for(let j=0;j<=150;j++){const a=j*Math.PI*2/150,rr=1.12+ring*.1;points.push(project(Math.cos(a)*rr,Math.sin(a)*(.2+ring*.16),Math.sin(a)*rr))}line(points,.24-ring*.04);
   const a=t*(.22+ring*.07)+ring*2.1,p=project(Math.cos(a)*(1.12+ring*.1),Math.sin(a)*(.2+ring*.16),Math.sin(a)*(1.12+ring*.1));ctx.beginPath();ctx.arc(p.x,p.y,3.2,0,Math.PI*2);ctx.fillStyle=ring===1?'#b79967':'#537db4';ctx.shadowColor=ring===1?'#c4a878':'#7099d1';ctx.shadowBlur=12;ctx.fill();ctx.shadowBlur=0;
  }
  for(let i=0;i<34;i++){const phi=Math.acos(1-2*(i+.5)/34),a=i*2.39996,p=project(Math.sin(phi)*Math.cos(a),Math.cos(phi),Math.sin(phi)*Math.sin(a));if(p.z<-.25)continue;ctx.beginPath();ctx.arc(p.x,p.y,1.4+(p.z+1)*.6,0,Math.PI*2);ctx.fillStyle=`rgba(57,100,164,${.35+(p.z+1)*.22})`;ctx.fill()}
 }
 function tick(now){if(last)t+=Math.min((now-last)/1000,.06);last=now;draw();raf=requestAnimationFrame(tick)}
 function sync(){cancelAnimationFrame(raf);last=0;draw();if(!reduced.matches&&!document.hidden&&document.body.classList.contains('is-home'))raf=requestAnimationFrame(tick)}
 new ResizeObserver(()=>{const box=canvas.getBoundingClientRect();width=box.width;height=box.height;const dpr=Math.min(devicePixelRatio||1,2);canvas.width=width*dpr;canvas.height=height*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);draw()}).observe(canvas);
 new MutationObserver(sync).observe(document.body,{attributes:true,attributeFilter:['class']});document.addEventListener('visibilitychange',sync);reduced.addEventListener('change',sync);sync();
})();
