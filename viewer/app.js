import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import {
  parseIFP,
  sampleTrack,
  buildSourceGlobalDeltas,
  retargetGlobalDeltasToSM64,
  buildSourceLocalBasis,
  buildTargetNodeSourceBone,
  buildClipTrackLookup,
  eulerXYZFromQuaternion,
  quantizeEulerSamples,
  sampleAngleChannels,
  fromWXYZ,
  quaternionMultiply,
  quaternionInverse,
  IDENTITY,
} from './core.js';

const FPS = 30;
const LOOP_CLIPS = new Set([
  'IDLE_stance', 'WALK_player', 'run_player', 'sprint_civi',
  'JUMP_glide', 'FALL_fall', 'FALL_glide', 'Swim_Tread',
]);
const SOURCE_PARENT_EXTENSIONS = {
  'arm left finger 1a': 'arm left wrist',
  'arm left finger 1b': 'arm left finger 1a',
  'arm right finger 1a': 'arm right wrist',
  'arm right finger 1b': 'arm right finger 1a',
  'leg left toes': 'leg left ankle',
  'leg right toes': 'leg right ankle',
  'head jaw': 'head neck upper',
  'head eyebrow left 1': 'head neck upper',
  'head eyebrow right 1': 'head neck upper',
};

const ui = {
  ifpInput: document.querySelector('#ifp-file'),
  clipSelect: document.querySelector('#clip-select'),
  play: document.querySelector('#play-button'),
  stepBack: document.querySelector('#step-back'),
  stepForward: document.querySelector('#step-forward'),
  reset: document.querySelector('#reset-button'),
  speed: document.querySelector('#speed-select'),
  timeline: document.querySelector('#timeline'),
  timeLabel: document.querySelector('#time-label'),
  status: document.querySelector('#status'),
  details: document.querySelector('#clip-details'),
  sourceStatus: document.querySelector('#source-status'),
  targetStatus: document.querySelector('#target-status'),
};

const state = {
  ifp: null,
  mapping: null,
  clips: [],
  selectedClip: null,
  source: null,
  target: null,
  sourceBoneMap: new Map(),
  targetBoneMap: new Map(),
  sourceRestLocal: {},
  targetRestLocal: {},
  sourceParents: {},
  targetNodeSourceBone: {},
  clipTrackLookup: {},
  targetAngleChannels: {},
  playing: false,
  elapsed: 0,
  speed: 1,
  lastTick: 0,
};

function setStatus(message, type = 'info') {
  ui.status.textContent = message;
  ui.status.dataset.type = type;
  document.querySelector('#status-dot').dataset.type = type;
}

function qObject(q) {
  return new THREE.Quaternion(q[0], q[1], q[2], q[3]);
}

function qArray(q) {
  return [q.x, q.y, q.z, q.w];
}

function qWxyzToThree(value) {
  return new THREE.Quaternion(value[1], value[2], value[3], value[0]);
}

function normalizeModel(root) {
  root.updateMatrixWorld(true);
  let bounds = new THREE.Box3().setFromObject(root);
  let dimensions = bounds.getSize(new THREE.Vector3());
  if (dimensions.x > dimensions.y * 1.12 && dimensions.x > dimensions.z * 1.12) {
    root.rotation.z += Math.PI / 2;
  } else if (dimensions.z > dimensions.y * 1.12 && dimensions.z > dimensions.x * 1.12) {
    root.rotation.x -= Math.PI / 2;
  }
  root.updateMatrixWorld(true);
  bounds = new THREE.Box3().setFromObject(root);
  dimensions = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const height = Math.max(dimensions.x, dimensions.y, dimensions.z);
  if (!Number.isFinite(height) || height <= 1e-5) throw new Error('Model bounds are invalid or empty.');
  const scale = 2.45 / height;
  root.scale.multiplyScalar(scale);
  root.position.x -= center.x * scale;
  root.position.z -= center.z * scale;
  root.position.y -= bounds.min.y * scale;
  root.updateMatrixWorld(true);
}

function collectBones(root) {
  const map = new Map();
  root.traverse((object) => {
    if (object.isBone) {
      const key = object.name.trim().toLocaleLowerCase('en-US');
      if (!map.has(key)) map.set(key, object);
    }
  });
  return map;
}

function createViewport(canvas, modelRoot) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111820);
  scene.add(modelRoot);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x4a5360, 2.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.3);
  key.position.set(3, 5, 4);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xb9d6ff, 0.8);
  fill.position.set(-4, 2, -3);
  scene.add(fill);
  scene.add(new THREE.GridHelper(4, 16, 0x45515c, 0x27313a));
  const camera = new THREE.PerspectiveCamera(34, 1, 0.01, 100);
  camera.up.set(0, 1, 0);
  camera.position.set(3.6, 2.25, 4.4);
  camera.lookAt(0, 1.1, 0);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 1.1, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.update();
  const container = canvas.parentElement;
  const resize = () => {
    const width = Math.max(1, container.clientWidth);
    const height = Math.max(1, container.clientHeight);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resize();
  return { scene, camera, renderer, controls, observer };
}

function extendSourceParents(mapping) {
  const parents = { ...mapping.source_parent_by_bone };
  for (const [bone, parent] of Object.entries(SOURCE_PARENT_EXTENSIONS)) {
    if (Object.hasOwn(mapping.source_rest_rotation_wxyz, bone)
        && Object.hasOwn(mapping.source_rest_rotation_wxyz, parent)) {
      parents[bone] = parent;
    }
  }
  return parents;
}

function buildRestLocalMap(restWxyz, parentByBone) {
  const result = {};
  for (const [name, restW] of Object.entries(restWxyz)) {
    const restGlobal = fromWXYZ(restW);
    const parent = parentByBone[name] ?? null;
    const parentGlobal = parent === null ? IDENTITY : fromWXYZ(restWxyz[parent]);
    const parentInverse = qObject(parentGlobal).invert();
    const local = parentInverse.multiply(qObject(restGlobal));
    result[name] = qArray(local);
  }
  return result;
}

function buildTargetRestLocalMap(mapping) {
  const result = {};
  for (const node of mapping.target_node_order) {
    const parentRest = mapping.target_parent_rest_rotation_wxyz[node] ?? [1, 0, 0, 0];
    const nodeRest = mapping.target_rest_rotation_wxyz[node];
    if (!nodeRest) throw new Error(`Target retarget map has no rest rotation for ${node}.`);
    const parentQ = qWxyzToThree(parentRest).invert();
    result[node] = qArray(parentQ.multiply(qWxyzToThree(nodeRest)));
  }
  return result;
}

function findAnimation(clipName) {
  const wanted = clipName.toLocaleLowerCase('en-US');
  return state.ifp.animations.find((clip) => clip.name.toLocaleLowerCase('en-US') === wanted) ?? null;
}

function buildSourcePoseLocal(trackLookup, timeSeconds) {
  const pose = {};
  for (const [boneName, track] of Object.entries(trackLookup)) {
    if (track.frames.length) pose[boneName] = sampleTrack(track, timeSeconds);
  }
  return pose;
}

function buildTargetAngles(clip) {
  const duration = clip.duration;
  const frameCount = Math.max(2, Math.ceil(duration * FPS - 1e-8) + 1);
  const times = Array.from({ length: frameCount }, (_, index) => index / FPS);
  if (times.at(-1) < duration - 1e-6) times.push(duration);
  const nodeFrames = Object.fromEntries(state.mapping.target_node_order.map((node) => [node, []]));
  for (const time of times) {
    const pose = buildSourcePoseLocal(state.clipTrackLookup, time);
    const sourceDeltas = buildSourceGlobalDeltas(
      state.sourceParents,
      state.mapping.source_rest_rotation_wxyz,
      pose,
      state.mapping.source_root_bone || 'root ground',
    );
    const retargeted = retargetGlobalDeltasToSM64(
      state.mapping.target_node_order,
      state.mapping.target_parent_animation_node,
      state.mapping.target_parent_rest_rotation_wxyz,
      state.targetNodeSourceBone,
      sourceDeltas,
      state.mapping.axis_alignment.quaternion_xyzw,
      'Body',
    );
    for (const node of state.mapping.target_node_order) {
      nodeFrames[node].push(eulerXYZFromQuaternion(retargeted.localChannels[node] ?? IDENTITY));
    }
  }
  return { channels: quantizeEulerSamples(nodeFrames), frameCount: times.length };
}

function prepareClip(clip) {
  state.selectedClip = clip;
  state.clipTrackLookup = buildClipTrackLookup(clip, state.mapping.source_track_to_bone);
  const targetTracks = new Set(Object.values(state.targetNodeSourceBone).filter(Boolean));
  const sourceTracks = Object.keys(state.clipTrackLookup);
  const sourceMapped = sourceTracks.filter((bone) => state.sourceBoneMap.has(bone.trim().toLocaleLowerCase('en-US'))).length;
  const targetMapped = sourceTracks.filter((bone) => targetTracks.has(bone)).length;
  state.targetAngleChannels = buildTargetAngles(clip);
  state.elapsed = 0;
  state.playing = false;
  ui.play.textContent = 'Reproducir';
  ui.timeline.max = String(clip.duration || 0.001);
  ui.timeline.value = '0';
  ui.details.textContent = `${clip.tracks.length} pistas IFP · ${sourceMapped} articulaciones disponibles en el rig GTA · ${targetMapped} pistas contribuyen a la portada · ${state.mapping.target_animation_node_count} nodos SM64. La pista raíz Normal/traslación se excluye del jugador, igual que en el conversor de juego.`;
  updatePose(0);
  updateTimeline();
}

function updatePose(timeSeconds) {
  if (!state.selectedClip || !state.mapping) return;
  const pose = buildSourcePoseLocal(state.clipTrackLookup, timeSeconds);
  const sourceDeltas = buildSourceGlobalDeltas(
    state.sourceParents,
    state.mapping.source_rest_rotation_wxyz,
    pose,
    state.mapping.source_root_bone || 'root ground',
  );
  const sourceBasis = buildSourceLocalBasis(state.mapping, sourceDeltas, state.sourceParents);
  for (const bone of state.sourceBoneMap.values()) {
    const boneName = bone.name;
    const restLocal = state.sourceRestLocal[boneName];
    const basis = sourceBasis[boneName];
    if (!restLocal || !basis) continue;
    const finalRotation = qObject(restLocal).multiply(qObject(basis));
    bone.quaternion.copy(finalRotation).normalize();
  }

  const framePosition = Math.max(0, Math.min(state.targetAngleChannels.frameCount - 1, timeSeconds * FPS));
  for (const node of state.mapping.target_node_order) {
    const bone = state.targetBoneMap.get(node.toLocaleLowerCase('en-US'));
    const restLocal = state.targetRestLocal[node];
    const channels = state.targetAngleChannels.channels[node];
    if (!bone || !restLocal || !channels) continue;
    const [x, y, z] = sampleAngleChannels(channels, framePosition);
    const animationRotation = new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z, 'XYZ'));
    bone.quaternion.copy(animationRotation.multiply(qObject(restLocal))).normalize();
  }
}

function updateTimeline() {
  const duration = state.selectedClip?.duration ?? 0;
  ui.timeline.value = String(Math.min(duration, state.elapsed));
  ui.timeLabel.textContent = `${state.elapsed.toFixed(2)} / ${duration.toFixed(2)} s`;
}

function stopPlayback() {
  state.playing = false;
  ui.play.textContent = 'Reproducir';
}

function renderLoop(timestamp) {
  requestAnimationFrame(renderLoop);
  if (state.lastTick === 0) state.lastTick = timestamp;
  const delta = Math.min(0.05, Math.max(0, (timestamp - state.lastTick) / 1000));
  state.lastTick = timestamp;
  if (state.playing && state.selectedClip) {
    state.elapsed += delta * state.speed;
    const duration = state.selectedClip.duration;
    if (state.elapsed >= duration) {
      if (LOOP_CLIPS.has(state.selectedClip.name)) state.elapsed %= Math.max(duration, 0.001);
      else { state.elapsed = duration; stopPlayback(); }
    }
    updatePose(state.elapsed);
    updateTimeline();
  }
  for (const viewport of [state.source?.viewport, state.target?.viewport]) {
    if (!viewport) continue;
    viewport.controls.update();
    viewport.renderer.render(viewport.scene, viewport.camera);
  }
}

async function loadJSON(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) throw new Error(`No se pudo cargar ${url} (${response.status}).`);
  return response.json();
}

async function loadModels() {
  setStatus('Cargando los modelos 3D y el mapa real del rig…');
  const loader = new GLTFLoader();
  const [sourceGLTF, targetGLTF, mapping] = await Promise.all([
    loader.loadAsync('./assets/cj64-gta-source.glb'),
    loader.loadAsync('./assets/cj64-sm64-target.glb'),
    loadJSON('./assets/cj64_sm64_animation_retarget_map.json'),
  ]);
  state.mapping = mapping;
  state.sourceParents = extendSourceParents(mapping);
  state.targetNodeSourceBone = buildTargetNodeSourceBone(mapping);
  state.source = { root: sourceGLTF.scene, viewport: null };
  state.target = { root: targetGLTF.scene, viewport: null };
  normalizeModel(state.source.root);
  normalizeModel(state.target.root);
  state.sourceBoneMap = collectBones(state.source.root);
  state.targetBoneMap = collectBones(state.target.root);
  state.sourceRestLocal = buildRestLocalMap(mapping.source_rest_rotation_wxyz, mapping.source_fbx_parent_by_bone);
  state.targetRestLocal = buildTargetRestLocalMap(mapping);

  const missingSource = Object.keys(mapping.source_rest_rotation_wxyz)
    .filter((name) => !state.sourceBoneMap.has(name.trim().toLocaleLowerCase('en-US')));
  const missingTarget = mapping.target_node_order
    .filter((name) => !state.targetBoneMap.has(name.trim().toLocaleLowerCase('en-US')));
  if (missingSource.length) throw new Error(`Rig GTA incompleto en GLB: ${missingSource.slice(0, 6).join(', ')}.`);
  if (missingTarget.length) throw new Error(`Rig SM64 incompleto en GLB: ${missingTarget.join(', ')}.`);

  state.source.viewport = createViewport(document.querySelector('#source-canvas'), state.source.root);
  state.target.viewport = createViewport(document.querySelector('#target-canvas'), state.target.root);
  ui.sourceStatus.textContent = `Rig GTA · ${state.sourceBoneMap.size} huesos`;
  ui.targetStatus.textContent = `Rig SM64 · ${mapping.target_animation_node_count} nodos de animación`;
  setStatus('Modelos listos. Selecciona el ped.ifp de tu dispositivo.');
}

function populateClipSelect() {
  const previous = ui.clipSelect.value;
  ui.clipSelect.replaceChildren();
  for (const clip of state.ifp.animations) {
    const option = document.createElement('option');
    option.value = clip.name;
    option.textContent = clip.name;
    ui.clipSelect.append(option);
  }
  const preferred = state.ifp.animations.find((clip) => clip.name === 'IDLE_stance');
  ui.clipSelect.value = previous && state.ifp.animations.some((clip) => clip.name === previous)
    ? previous : preferred?.name ?? state.ifp.animations[0]?.name ?? '';
  ui.clipSelect.disabled = state.ifp.animations.length === 0;
  ui.clipSelect.dispatchEvent(new Event('change'));
}

ui.ifpInput.addEventListener('change', async () => {
  const file = ui.ifpInput.files?.[0];
  if (!file) return;
  try {
    stopPlayback();
    setStatus(`Leyendo ${file.name}…`);
    const parsed = parseIFP(await file.arrayBuffer());
    if (parsed.animations.length === 0) throw new Error('El paquete IFP no contiene animaciones.');
    state.ifp = parsed;
    populateClipSelect();
    setStatus(`IFP ${parsed.packageName}: ${parsed.animations.length} animaciones leídas (${(file.size / 1024 / 1024).toFixed(2)} MB).`, 'success');
  } catch (error) {
    console.error(error);
    setStatus(error.message || 'No se pudo leer el archivo IFP.', 'error');
  }
});

ui.clipSelect.addEventListener('change', () => {
  if (!state.ifp) return;
  const clip = findAnimation(ui.clipSelect.value);
  if (!clip) return;
  try {
    prepareClip(clip);
    setStatus(`Comparando ${clip.name}.`, 'success');
  } catch (error) {
    console.error(error);
    setStatus(`No se pudo preparar ${clip.name}: ${error.message}`, 'error');
  }
});

ui.play.addEventListener('click', () => {
  if (!state.selectedClip) return;
  if (state.playing) stopPlayback();
  else {
    if (state.elapsed >= state.selectedClip.duration) state.elapsed = 0;
    state.playing = true;
    ui.play.textContent = 'Pausar';
  }
});
ui.stepBack.addEventListener('click', () => {
  stopPlayback();
  state.elapsed = Math.max(0, state.elapsed - 1 / FPS);
  updatePose(state.elapsed);
  updateTimeline();
});
ui.stepForward.addEventListener('click', () => {
  stopPlayback();
  state.elapsed = Math.min(state.selectedClip?.duration ?? 0, state.elapsed + 1 / FPS);
  updatePose(state.elapsed);
  updateTimeline();
});
ui.reset.addEventListener('click', () => {
  stopPlayback();
  state.elapsed = 0;
  updatePose(0);
  updateTimeline();
});
ui.speed.addEventListener('change', () => { state.speed = Number(ui.speed.value) || 1; });
ui.timeline.addEventListener('input', () => {
  stopPlayback();
  state.elapsed = Number(ui.timeline.value) || 0;
  updatePose(state.elapsed);
  updateTimeline();
});

try {
  await loadModels();
  requestAnimationFrame(renderLoop);
} catch (error) {
  console.error(error);
  setStatus(`Error al preparar el visor: ${error.message}`, 'error');
  ui.sourceStatus.textContent = 'No disponible';
  ui.targetStatus.textContent = 'No disponible';
}
