import test from 'node:test';
import assert from 'node:assert/strict';
import {
  parseIFP,
  sampleTrack,
  buildSourceGlobalDeltas,
  retargetGlobalDeltasToSM64,
  buildSourceLocalBasis,
  angle16,
  quantizeEulerSamples,
} from './core.js';

function fixed(value, size) {
  const bytes = Buffer.from(value, 'latin1');
  const out = Buffer.alloc(size);
  bytes.copy(out, 0, 0, Math.min(bytes.length, size - 1));
  return out;
}

function makeIFP() {
  const track = Buffer.concat([
    fixed(' Normal', 24), Buffer.from([3,0,0,0,2,0,0,0,0,0,0,0]),
    Buffer.from([0,0,0,0,0,0,0,16,0,0]),
    Buffer.from([0,0,0,0,0,0,0,16,30,0]),
  ]);
  const anim = Buffer.concat([
    fixed('IDLE_stance', 24), Buffer.from([1,0,0,0,42,0,0,0,1,0,0,0]), track,
  ]);
  const body = Buffer.concat([fixed('ped',24),Buffer.from([1,0,0,0]),anim]);
  const header = Buffer.alloc(8);
  header.write('ANP3',0,'ascii');
  header.writeUInt32LE(body.length,4);
  return Buffer.concat([header,body]);
}

const identity = [0,0,0,1];
function qAxis(axis, angle) {
  const s = Math.sin(angle/2);
  return [axis[0]*s,axis[1]*s,axis[2]*s,Math.cos(angle/2)];
}
function quatNear(a,b,eps=1e-6) {
  const direct = Math.max(...a.map((v,i)=>Math.abs(v-b[i])));
  const opposite = Math.max(...a.map((v,i)=>Math.abs(v+b[i])));
  assert.ok(Math.min(direct,opposite)<eps, `quaternions differ: ${a} vs ${b}`);
}

test('parses ANP3 IFP tracks, frame times and normalizes quaternions', () => {
  const raw = makeIFP();
  const parsed = parseIFP(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength));
  assert.equal(parsed.packageName.toLowerCase(),'ped');
  assert.equal(parsed.animations.length,1);
  const idle = parsed.animations[0];
  assert.equal(idle.name,'IDLE_stance');
  assert.equal(idle.tracks[0].name.trim(),'Normal');
  assert.equal(idle.tracks[0].frames.length,2);
  assert.equal(idle.tracks[0].frames[1].timeSeconds,0.5);
  quatNear(idle.tracks[0].frames[0].rotation,identity);
});

test('rejects invalid or truncated IFP data', () => {
  assert.throws(()=>parseIFP(new Uint8Array([1,2,3,4]).buffer),/small|ANP3/);
  const valid = makeIFP();
  const truncated = valid.slice(0, -2);
  assert.throws(()=>parseIFP(truncated.buffer.slice(truncated.byteOffset, truncated.byteOffset + truncated.byteLength)),/truncated|Unexpected|range/i);
});

test('samples tracks with quaternion interpolation', () => {
  const track = {frames:[
    {timeSeconds:0,rotation:identity},
    {timeSeconds:1,rotation:qAxis([0,0,1],Math.PI)},
  ]};
  const mid = sampleTrack(track,0.5);
  quatNear(mid,qAxis([0,0,1],Math.PI/2));
});

test('keeps GTA root Normal out of player-root deltas', () => {
  const rest={root:identity,pelvis:qAxis([0,0,1],0.2)};
  const parents={root:null,pelvis:'root'};
  const deltas=buildSourceGlobalDeltas(parents,rest,{root:qAxis([0,1,0],Math.PI/2),pelvis:qAxis([1,0,0],0.4)},'root');
  quatNear(deltas.root,identity);
  assert.notDeepEqual(deltas.pelvis,identity);
});

test('retargets a source hierarchy delta into a different SM64 parent hierarchy', () => {
  const sourceDeltas={root:identity,pelvis:qAxis([0,0,1],0.2),neck:qAxis([1,0,0],0.45),shoulder:qAxis([0,1,0],-0.15)};
  const nodes=['Body','Butt','Torso','Head','Left Arm'];
  const parents={Body:null,Butt:'Body',Torso:'Butt',Head:'Torso','Left Arm':'Torso'};
  const parentRest={Body:identity,Butt:identity,Torso:identity,Head:identity,'Left Arm':qAxis([0,0,1],0.3)};
  const sources={Body:null,Butt:'pelvis',Torso:null,Head:'neck','Left Arm':'shoulder'};
  const align=qAxis([0,0,1],-Math.PI/2);
  const result=retargetGlobalDeltasToSM64(nodes,parents,parentRest,sources,sourceDeltas,align);
  assert.equal(Object.keys(result.localChannels).length,5);
  quatNear(result.localChannels.Body,identity);
  assert.ok(result.targetGlobalDeltas['Left Arm'].every(Number.isFinite));
  assert.notDeepEqual(result.localChannels['Left Arm'],sourceDeltas.shoulder);
});

test('builds local source basis using actual FBX parent tree', () => {
  const mapping={
    source_rest_rotation_wxyz:{'root ground':[1,0,0,0],pelvis:[Math.cos(.1),0,0,Math.sin(.1)]},
    source_fbx_parent_by_bone:{'root ground':null,pelvis:'root ground'},
    source_parent_by_bone:{'root ground':null,pelvis:'root ground'},
    source_track_to_bone:{normal:'root ground',pelvis:'pelvis'},
  };
  const deltas={ 'root ground':identity, pelvis:qAxis([0,1,0],.5) };
  const result=buildSourceLocalBasis(mapping,deltas);
  assert.equal(result.pelvis.length,4);
  assert.ok(result.pelvis.every(Number.isFinite));
});

test('quantizes and unwraps 16-bit Euler angle samples across the wrap boundary', () => {
  const values=quantizeEulerSamples({Body:[[3.13,0,0],[-3.13,0,0]]});
  assert.equal(values.Body[0].length,2);
  assert.ok(Math.abs(values.Body[0][1]-values.Body[0][0])<1000);
  assert.equal(angle16(0),0);
});

test('composes animation delta after the bind-pose local rotation', async () => {
  const { composeRestAndPose } = await import('./core.js');
  const rest=qAxis([0,0,1],Math.PI/2);
  const delta=qAxis([1,0,0],Math.PI/3);
  const actual=composeRestAndPose(rest,delta);
  const expected=(await import('./core.js')).quaternionMultiply(rest,delta);
  const wrong=(await import('./core.js')).quaternionMultiply(delta,rest);
  quatNear(actual,expected);
  assert.ok(Math.max(...actual.map((v,i)=>Math.abs(v-wrong[i])))>0.1);
});
