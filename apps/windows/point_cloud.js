'use strict';
const $=id=>document.getElementById(id), canvas=$('cloud');
const gl=canvas.getContext('webgl',{antialias:true});
let latest=null, displayed=null, data=null, paused=false, reachable=false, state=null;
let stateAt=0, shownAt=0, shownAge=null, lastKey=null, count=0, centerZ=.5;
let yaw=0,pitch=0,zoom=1,panX=0,panY=0, program,buffer;
const fmt=(v,d=2)=>Number.isFinite(v)?v.toFixed(d):'—';
function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;}
function init(){
  if(!gl)throw new Error('WebGL no está disponible en este navegador.');
  program=gl.createProgram();
  gl.attachShader(program,shader(gl.VERTEX_SHADER,`
    attribute vec3 point; uniform float yaw,pitch,zoom,aspect,centerZ,size,nearZ,farZ;
    uniform vec2 pan; varying vec3 color;
    void main(){
      vec3 p=vec3(point.x,-point.y,centerZ-point.z);
      p=vec3(cos(yaw)*p.x+sin(yaw)*p.z,p.y,-sin(yaw)*p.x+cos(yaw)*p.z);
      p=vec3(p.x,cos(pitch)*p.y-sin(pitch)*p.z,sin(pitch)*p.y+cos(pitch)*p.z);
      gl_Position=vec4((p.x*zoom+pan.x)/aspect,p.y*zoom+pan.y,-p.z/20.0,1.0);
      gl_PointSize=size;
      float t=clamp((point.z-nearZ)/(farZ-nearZ),0.0,1.0);
      color=mix(vec3(.12,.65,1.0),vec3(1.0,.86,.25),t);
    }`));
  gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`precision mediump float; varying vec3 color;
    void main(){if(distance(gl_PointCoord,vec2(.5))>.5)discard;gl_FragColor=vec4(color,1.0);}`));
  gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('No se pudo iniciar el visor WebGL.');
  gl.useProgram(program);buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  const location=gl.getAttribLocation(program,'point');gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,3,gl.FLOAT,false,0,0);
  gl.enable(gl.DEPTH_TEST);gl.clearColor(.039,.067,.094,1);
}
function render(){
  if(!program)return;
  const ratio=Math.min(devicePixelRatio||1,2),w=Math.round(canvas.clientWidth*ratio),h=Math.round(canvas.clientHeight*ratio);
  if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
  gl.viewport(0,0,w,h);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  for(const [key,value] of Object.entries({yaw,pitch,zoom,aspect:w/h,centerZ,size:Number($('size').value)*ratio,nearZ:Number($('near').value),farZ:Number($('far').value)}))gl.uniform1f(gl.getUniformLocation(program,key),value);
  gl.uniform2f(gl.getUniformLocation(program,'pan'),panX,panY);gl.drawArrays(gl.POINTS,0,count);
}
function rebuild(){
  if(!data||!program)return;
  try{
    const cloud=CloudMath.project(displayed.header,data,Number($('near').value),Number($('far').value),Number($('stride').value));
    count=cloud.count;centerZ=cloud.centerZ;
    gl.bufferData(gl.ARRAY_BUFFER,cloud.points,gl.DYNAMIC_DRAW);
    $('frame').textContent=`Frame ${displayed.header.frame_id} · ${displayed.header.width} × ${displayed.header.height} · ${count.toLocaleString()} puntos · SHA-256 verificado`;
    $('error').textContent=count?'':'No hay puntos dentro del rango seleccionado.';
  }catch(error){count=0;$('error').textContent=error.message;$('frame').textContent='Frame recibido sin nube proyectable.';}
  render();
}
function showLatest(){
  if(!latest||paused)return;
  const h=latest.header,key=JSON.stringify([h.frame_id,h.timestamp,state?.timings?.ios_session_id]);
  if(key===lastKey)return;lastKey=key;
  displayed=latest;shownAge=state.unique_age_s;shownAt=performance.now();
  const bytes=Uint8Array.from(atob(latest.raw),c=>c.charCodeAt(0));data=new DataView(bytes.buffer);
  $('title').textContent=h.source==='synthetic-demo'?'DEMO SINTÉTICA · nube de puntos':'iPhone TrueDepth · nube de puntos';
  $('metadata').textContent=JSON.stringify(h,null,2);rebuild();
}
function tick(){
  const now=performance.now(),age=state?.unique_age_s==null?null:state.unique_age_s+(now-stateAt)/1000;
  const label=CloudMath.freshness({finished:state?.finished,paused,age,reachable});
  $('badge').textContent=label;$('badge').dataset.live=label==='En vivo';
  const displayAge=shownAge===null?null:shownAge+(now-shownAt)/1000;
  $('age').textContent=`Último frame distinto recibido: ${fmt(age,1)} s${paused?' · vista congelada: '+fmt(displayAge,1)+' s':''}`;
}
async function poll(){
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),1500);
  try{
    const response=await fetch('/state',{cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error('HTTP '+response.status);
    state=await response.json();stateAt=performance.now();reachable=true;latest=state.frame;
    $('receiver').textContent=state.status;
    const m=state.metrics,t=state.timings??{};
    const entries=[['Recibidos / errores',`${m.received??0} / ${m.errors??0}`],['Frecuencia media',fmt(m.received_hz)+' Hz'],['Mayor pausa entre válidos',fmt(m.max_valid_gap_s)+' s'],['Duplicados / discontinuidades',`${m.duplicates??0} / ${m.discontinuities??0}`],['Transporte / conexiones',`${state.transport??'—'} / ${state.connections??0}`],['Payload / validación',`${fmt(t.payload_receive_ms)} / ${fmt(t.validation_ms)} ms`]];
    $('metrics').replaceChildren(...entries.flatMap(([a,b])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=a;dd.textContent=b;return [dt,dd];}));
    showLatest();
  }catch(error){reachable=false;$('receiver').textContent='Receptor no disponible: '+error.message;}
  finally{clearTimeout(timeout);tick();setTimeout(poll,200);}
}
$('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'Reanudar vista':'Pausar vista';showLatest();tick();};
$('reset').onclick=()=>{yaw=pitch=panX=panY=0;zoom=1;render();};
for(const id of ['near','far','stride'])$(id).onchange=rebuild;
$('size').oninput=render;
let drag=null;
canvas.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);};
canvas.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag={x:e.clientX,y:e.clientY};if(e.shiftKey){panX+=dx*2/canvas.clientHeight;panY-=dy*2/canvas.clientHeight;}else{yaw+=dx*.01;pitch+=dy*.01;}render();};
canvas.onpointerup=canvas.onpointercancel=()=>drag=null;
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.1,Math.min(30,zoom*Math.exp(-e.deltaY*.001)));render();},{passive:false});
new ResizeObserver(render).observe(canvas);
try{init();render();}catch(error){program=null;$('error').textContent=error.message;}
setInterval(tick,100);poll();
