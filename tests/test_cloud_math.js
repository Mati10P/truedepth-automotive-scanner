const {test}=require('node:test');
const assert=require('node:assert/strict');
const {intrinsics,project,freshness}=require('../apps/windows/cloud_math.js');
const h={width:4,height:2,calibration:{intrinsic_matrix_rows:[[4,0,2],[0,4,2],[0,0,1]],intrinsic_reference_width:8,intrinsic_reference_height:4}};
function depth(values){const d=new DataView(new ArrayBuffer(values.length*4));values.forEach((v,i)=>d.setFloat32(i*4,v,true));return d;}
test('reference resolution scales intrinsics, plane has correct metric coordinates',()=>{
  assert.deepEqual(intrinsics(h),{fx:2,fy:2,cx:1,cy:1});
  const cloud=project(h,depth(Array(8).fill(1)),.2,2,1);
  assert.equal(cloud.count,8);assert.deepEqual(Array.from(cloud.points.slice(0,6)),[-.5,-.5,1,0,-.5,1]);
  assert.deepEqual(Array.from(cloud.points.slice(15,18)),[0,0,1]);
});
test('reject invalid depths and crop, sample bounded point count',()=>{
  assert.equal(project(h,depth([NaN,Infinity,0,-1,.1,.5,1,2]),.2,1,1).count,2);
  assert.equal(project(h,depth(Array(8).fill(1)),.2,2,2).count,2);
  assert.equal(project(h,depth(Array(8).fill(0)),.2,2,1).count,0);
});
test('never invent intrinsics; reject malformed projection and buffers',()=>{
  assert.throws(()=>intrinsics({...h,calibration:null}));
  assert.throws(()=>intrinsics({...h,calibration:{...h.calibration,intrinsic_reference_width:0}}));
  assert.throws(()=>project(h,depth([1]),.2,1,1));
  for(const args of [[1,.2,1],[NaN,1,1],[.2,1,0]])assert.throws(()=>project(h,depth(Array(8).fill(1)),...args));
});
test('observed 2.24 second stall is stale; recovery, disconnection, pause and completion explicit',()=>{
  assert.equal(freshness({age:.2}),'En vivo');
  assert.equal(freshness({age:.7}),'Datos demorados');
  assert.equal(freshness({age:2.24}),'Sin frame nuevo');
  assert.equal(freshness({age:.1}),'En vivo');
  assert.equal(freshness({age:null}),'Esperando primer frame');
  assert.equal(freshness({reachable:false,age:.1}),'Receptor no disponible');
  assert.equal(freshness({paused:true,age:3}),'Inspección pausada');
  assert.equal(freshness({finished:true,age:.1}),'Sesión terminada');
});
