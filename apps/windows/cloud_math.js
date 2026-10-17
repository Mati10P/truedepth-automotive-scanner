/* Pinhole preview in camera coordinates (x right, y down, z forward), meters.
   Deliberately no lens rectification, pose estimation or frame fusion. */
(function(root) {
  'use strict';
  function intrinsics(h) {
    const c=h.calibration, k=c?.intrinsic_matrix_rows;
    if (!c || !Array.isArray(k) || k.length!==3 ||
        !k.every(row=>Array.isArray(row)&&row.length===3&&row.every(Number.isFinite)) ||
        ![c.intrinsic_reference_width,c.intrinsic_reference_height,h.width,h.height].every(v=>Number.isFinite(v)&&v>0) ||
        k[0][0]<=0 || k[1][1]<=0 || k[0][1]!==0 || k[1][0]!==0 ||
        k[2][0]!==0 || k[2][1]!==0 || k[2][2]!==1) {
      throw new Error('Sin intrínsecos compatibles: no se puede proyectar la nube.');
    }
    const sx=h.width/c.intrinsic_reference_width, sy=h.height/c.intrinsic_reference_height;
    return {fx:k[0][0]*sx,fy:k[1][1]*sy,cx:k[0][2]*sx,cy:k[1][2]*sy};
  }
  function project(h, data, near, far, stride) {
    const k=intrinsics(h);
    if (!Number.isFinite(near)||!Number.isFinite(far)||near<=0||far<=near ||
        !Number.isInteger(stride)||stride<1) throw new Error('Rango o muestreo inválido.');
    if (data.byteLength!==h.width*h.height*4) throw new Error('Depth incompleto.');
    const points=new Float32Array(Math.ceil(h.width/stride)*Math.ceil(h.height/stride)*3);
    let n=0, sumZ=0;
    for(let y=0;y<h.height;y+=stride) for(let x=0;x<h.width;x+=stride) {
      const z=data.getFloat32((y*h.width+x)*4,true);
      if(!Number.isFinite(z)||z<near||z>far)continue;
      points[n++]=(x-k.cx)*z/k.fx;
      points[n++]=(y-k.cy)*z/k.fy;
      points[n++]=z; sumZ+=z;
    }
    return {points:points.subarray(0,n),count:n/3,centerZ:n?sumZ/(n/3):.5};
  }
  function freshness({finished=false, paused=false, age=null, reachable=true}) {
    if(paused)return 'Inspección pausada';
    if(!reachable)return 'Receptor no disponible';
    if(finished)return 'Sesión terminada';
    if(age===null)return 'Esperando primer frame';
    if(age>=2)return 'Sin frame nuevo';
    if(age>=.6)return 'Datos demorados';
    return 'En vivo';
  }
  const api={intrinsics,project,freshness};
  if(typeof module!=='undefined')module.exports=api;
  else root.CloudMath=api;
})(globalThis);
