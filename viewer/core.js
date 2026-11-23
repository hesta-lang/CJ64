const IDENTITY = Object.freeze([0, 0, 0, 1]);
const MAX_ANIMATIONS = 4096;
const MAX_TRACKS = 256;
const MAX_FRAMES = 100000;

function normaliseQuaternion(q) {
  const length = Math.hypot(q[0], q[1], q[2], q[3]);
  if (!Number.isFinite(length) || length < 1e-10) {
    throw new Error('IFP contains a zero-length or invalid quaternion.');
  }
  return q.map((value) => value / length);
}

function quaternionMultiply(a, b) {
  const [ax, ay, az, aw] = normaliseQuaternion(a);
  const [bx, by, bz, bw] = normaliseQuaternion(b);
  return normaliseQuaternion([
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
    aw * bw - ax * bx - ay * by - az * bz,
  ]);
}

function quaternionInverse(q) {
  const [x, y, z, w] = normaliseQuaternion(q);
  return [-x, -y, -z, w];
}

function quaternionSlerp(a, b, amount) {
  a = normaliseQuaternion(a);
  b = normaliseQuaternion(b);
  let dot = a.reduce((sum, value, index) => sum + value * b[index], 0);
  if (dot < 0) {
    b = b.map((value) => -value);
    dot = -dot;
  }
  dot = Math.max(-1, Math.min(1, dot));
  if (dot > 0.9995) {
    return normaliseQuaternion(a.map((value, index) => value + amount * (b[index] - value)));
  }
  const theta = Math.acos(dot);
  const sine = Math.sin(theta);
  const wa = Math.sin((1 - amount) * theta) / sine;
  const wb = Math.sin(amount * theta) / sine;
  return normaliseQuaternion(a.map((value, index) => wa * value + wb * b[index]));
}

function fromWXYZ(q) {
  return normaliseQuaternion([q[1], q[2], q[3], q[0]]);
}

function topologicalOrder(parents, rest, rootBone) {
  if (!Object.hasOwn(rest, rootBone)) throw new Error(`Missing source rest bone: ${rootBone}`);
  const order = [];
  const visiting = new Set();
  const visited = new Set();
  function visit(name) {
    if (visited.has(name)) return;
    if (visiting.has(name)) throw new Error(`Cycle in source skeleton hierarchy at ${name}`);
    if (!Object.hasOwn(rest, name)) throw new Error(`Missing rest rotation for ${name}`);
    visiting.add(name);
    const parent = parents[name] ?? null;
    if (parent !== null) {
      if (!Object.hasOwn(rest, parent)) throw new Error(`Missing rest rotation for parent ${parent} of ${name}`);
      visit(parent);
    }
    visiting.delete(name);
    visited.add(name);
    order.push(name);
  }
  for (const name of Object.keys(rest)) visit(name);
  if ((parents[rootBone] ?? null) !== null) throw new Error('Configured source root must have no parent.');
  return order;
}

export function parseIFP(buffer) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 36) {
    throw new Error('The selected file is empty or too small to be an IFP package.');
  }
  const view = new DataView(buffer);
  let offset = 0;
  const decoder = new TextDecoder('latin1');
  function readBytes(length) {
    if (offset + length > view.byteLength) throw new Error(`Truncated IFP file at byte ${offset}.`);
    const bytes = new Uint8Array(buffer, offset, length);
    offset += length;
    return bytes;
  }
  function readU32() {
    if (offset + 4 > view.byteLength) throw new Error(`Truncated IFP integer at byte ${offset}.`);
    const value = view.getUint32(offset, true);
    offset += 4;
    return value;
  }
  function readI16() {
    if (offset + 2 > view.byteLength) throw new Error(`Truncated IFP keyframe at byte ${offset}.`);
    const value = view.getInt16(offset, true);
    offset += 2;
    return value;
  }
  function readFixedString(length) {
    const bytes = readBytes(length);
    let end = bytes.indexOf(0);
    if (end < 0) end = bytes.length;
    return decoder.decode(bytes.subarray(0, end)).replace(/[\s\0]+$/g, '');
  }

  const magic = decoder.decode(readBytes(4));
  if (magic !== 'ANP3') throw new Error(`Unsupported IFP format '${magic}'; expected ANP3.`);
  const declaredSize = readU32();
  const packageName = readFixedString(24);
  const animationCount = readU32();
  if (animationCount > MAX_ANIMATIONS) throw new Error(`Unreasonable IFP animation count: ${animationCount}.`);
  const animations = [];

  for (let animationIndex = 0; animationIndex < animationCount; animationIndex += 1) {
    const name = readFixedString(24);
    const trackCount = readU32();
    readU32(); // frame data size, informational in current ANP3 variants
    readU32(); // reserved
    if (trackCount > MAX_TRACKS) throw new Error(`Animation '${name}' has too many bone tracks.`);
    const tracks = [];
    for (let trackIndex = 0; trackIndex < trackCount; trackIndex += 1) {
      const trackName = readFixedString(24);
      const keyType = readU32();
      const frameCount = readU32();
      const boneId = readU32();
      if (keyType !== 3 && keyType !== 4) throw new Error(`Unsupported IFP key type ${keyType} in '${name}/${trackName}'.`);
      if (frameCount > MAX_FRAMES) throw new Error(`Animation '${name}' has too many keyframes in '${trackName}'.`);
      const frames = [];
      for (let frameIndex = 0; frameIndex < frameCount; frameIndex += 1) {
        const q = normaliseQuaternion([
          readI16() / 4096,
          readI16() / 4096,
          readI16() / 4096,
          readI16() / 4096,
        ]);
        const timeSeconds = readI16() / 60;
        let translation = null;
        if (keyType === 4) {
          translation = [readI16() / 4096, readI16() / 4096, readI16() / 4096];
        }
        frames.push({ timeSeconds, rotation: q, translation });
      }
      tracks.push({ name: trackName, normalizedName: trackName.trim().toLocaleLowerCase('en-US'), boneId, keyType, frames });
    }
    const duration = tracks.reduce((max, track) => Math.max(max, track.frames.at(-1)?.timeSeconds ?? 0), 0);
    animations.push({ name, tracks, duration });
  }

  const trailing = new Uint8Array(buffer, offset);
  if (trailing.some((value) => value !== 0)) throw new Error(`Unexpected non-padding data after IFP payload (${trailing.length} bytes).`);
  if (declaredSize !== buffer.byteLength - 8 && declaredSize !== offset - 8) {
    // The field has differed between ANP3 writers; exact parse bounds above are authoritative.
  }
  return { packageName, animations, bytes: buffer.byteLength };
}

export function sampleTrack(track, timeSeconds) {
  const frames = track?.frames ?? [];
  if (frames.length === 0) return [...IDENTITY];
  if (frames.length === 1 || timeSeconds <= frames[0].timeSeconds) return [...frames[0].rotation];
  if (timeSeconds >= frames.at(-1).timeSeconds) return [...frames.at(-1).rotation];
  let low = 0;
  while (low + 1 < frames.length && frames[low + 1].timeSeconds < timeSeconds) low += 1;
  const first = frames[low];
  const second = frames[low + 1];
  const span = second.timeSeconds - first.timeSeconds;
  const amount = span <= 1e-9 ? 0 : (timeSeconds - first.timeSeconds) / span;
  return quaternionSlerp(first.rotation, second.rotation, amount);
}

export function sampleTrackTranslation(track, timeSeconds) {
  const frames = track?.frames ?? [];
  if (frames.length === 0 || frames.every((frame) => frame.translation == null)) return null;
  const sample = (frame) => frame.translation ?? [0, 0, 0];
  if (frames.length === 1 || timeSeconds <= frames[0].timeSeconds) return [...sample(frames[0])];
  if (timeSeconds >= frames.at(-1).timeSeconds) return [...sample(frames.at(-1))];
  let low = 0;
  while (low + 1 < frames.length && frames[low + 1].timeSeconds < timeSeconds) low += 1;
  const first = frames[low];
  const second = frames[low + 1];
  const span = second.timeSeconds - first.timeSeconds;
  const amount = span <= 1e-9 ? 0 : (timeSeconds - first.timeSeconds) / span;
  const a = sample(first);
  const b = sample(second);
  return a.map((value, axis) => value + (b[axis] - value) * amount);
}

export function buildSourceGlobalDeltas(sourceParents, sourceRestWXYZ, sourcePoseLocal, rootBone = 'root ground') {
  const rest = Object.fromEntries(Object.entries(sourceRestWXYZ).map(([name, q]) => [name, fromWXYZ(q)]));
  const order = topologicalOrder(sourceParents, rest, rootBone);
  const currentGlobal = {};
  const deltas = {};
  for (const name of order) {
    const parent = sourceParents[name] ?? null;
    if (name === rootBone || parent === null) {
      currentGlobal[name] = rest[name];
      deltas[name] = [...IDENTITY];
      continue;
    }
    const localRest = quaternionMultiply(quaternionInverse(rest[parent]), rest[name]);
    const poseDelta = normaliseQuaternion(sourcePoseLocal[name] ?? IDENTITY);
    currentGlobal[name] = quaternionMultiply(quaternionMultiply(currentGlobal[parent], localRest), poseDelta);
    deltas[name] = quaternionMultiply(currentGlobal[name], quaternionInverse(rest[name]));
  }
  return deltas;
}

export function retargetGlobalDeltasToSM64(targetNodes, targetParentNodes, targetParentRestWXYZ, targetNodeSourceBone, sourceGlobalDeltas, axisAlignmentXYZW, rootNode = 'Body') {
  const align = normaliseQuaternion(axisAlignmentXYZW);
  const alignInverse = quaternionInverse(align);
  const localChannels = {};
  const targetGlobalDeltas = {};
  const parentRest = Object.fromEntries(Object.entries(targetParentRestWXYZ).map(([name, q]) => [name, fromWXYZ(q)]));
  for (const node of targetNodes) {
    if (node === rootNode) {
      localChannels[node] = [...IDENTITY];
      targetGlobalDeltas[node] = [...IDENTITY];
      continue;
    }
    const parentNode = targetParentNodes[node] ?? null;
    if (parentNode !== null && !Object.hasOwn(targetGlobalDeltas, parentNode)) {
      throw new Error(`Target parent '${parentNode}' must precede node '${node}'.`);
    }
    const parentDelta = targetGlobalDeltas[parentNode] ?? IDENTITY;
    const parentRestRotation = parentRest[node] ?? IDENTITY;
    const sourceBone = targetNodeSourceBone[node];
    if (!sourceBone) {
      localChannels[node] = [...IDENTITY];
      targetGlobalDeltas[node] = [...parentDelta];
      continue;
    }
    if (!Object.hasOwn(sourceGlobalDeltas, sourceBone)) throw new Error(`Missing source delta '${sourceBone}' for target node '${node}'.`);
    const desiredGlobal = quaternionMultiply(quaternionMultiply(align, sourceGlobalDeltas[sourceBone]), alignInverse);
    const local = quaternionMultiply(
      quaternionMultiply(
        quaternionMultiply(quaternionInverse(parentRestRotation), quaternionInverse(parentDelta)),
        desiredGlobal,
      ),
      parentRestRotation,
    );
    localChannels[node] = normaliseQuaternion(local);
    targetGlobalDeltas[node] = quaternionMultiply(
      quaternionMultiply(quaternionMultiply(parentDelta, parentRestRotation), localChannels[node]),
      quaternionInverse(parentRestRotation),
    );
  }
  return { localChannels, targetGlobalDeltas };
}

export function buildSourceLocalBasis(mapping, sourceGlobalDeltas, sourceIfpParents = mapping.source_parent_by_bone) {
  const restWXYZ = mapping.source_rest_rotation_wxyz;
  const rest = Object.fromEntries(Object.entries(restWXYZ).map(([name, q]) => [name, fromWXYZ(q)]));
  const parents = mapping.source_fbx_parent_by_bone;
  const order = topologicalOrder(parents, rest, 'root ground');
  const desiredGlobal = {};
  const localBasis = {};
  for (const name of order) {
    const parent = parents[name] ?? null;
    const localRest = parent === null ? rest[name] : quaternionMultiply(quaternionInverse(rest[parent]), rest[name]);
    if (Object.hasOwn(sourceGlobalDeltas, name) && Object.hasOwn(sourceIfpParents, name)) {
      desiredGlobal[name] = quaternionMultiply(sourceGlobalDeltas[name], rest[name]);
    } else {
      desiredGlobal[name] = parent === null ? rest[name] : quaternionMultiply(desiredGlobal[parent], localRest);
    }
    const parentCurrent = parent === null ? IDENTITY : desiredGlobal[parent];
    localBasis[name] = quaternionMultiply(
      quaternionMultiply(quaternionInverse(localRest), quaternionInverse(parentCurrent)),
      desiredGlobal[name],
    );
  }
  return localBasis;
}

export function composeRestAndPose(restLocal, poseDelta) {
  // Blender pose channels are deltas applied after each bone's local bind pose.
  return quaternionMultiply(restLocal, poseDelta);
}

export function eulerXYZFromQuaternion(q) {
  const [x, y, z, w] = normaliseQuaternion(q);
  const rx = Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y));
  const sinY = 2 * (w * y - z * x);
  const ry = Math.abs(sinY) >= 1 ? Math.sign(sinY) * Math.PI / 2 : Math.asin(sinY);
  const rz = Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z));
  return [rx, ry, rz];
}

export function angle16(radians) {
  return Math.round(radians * 65536 / (2 * Math.PI)) & 0xffff;
}

export function quantizeEulerSamples(eulerFramesByNode) {
  const result = {};
  for (const [node, frames] of Object.entries(eulerFramesByNode)) {
    if (!frames.length) { result[node] = [[], [], []]; continue; }
    const axes = [0, 1, 2].map((axis) => frames.map((frame) => angle16(frame[axis])));
    for (const samples of axes) {
      for (let index = 1; index < samples.length; index += 1) {
        while (samples[index] - samples[index - 1] > 32768) samples[index] -= 65536;
        while (samples[index] - samples[index - 1] < -32768) samples[index] += 65536;
      }
    }
    result[node] = axes;
  }
  return result;
}

export function sampleAngleChannels(channels, framePosition) {
  const maxFrames = channels[0]?.length ?? 0;
  if (!maxFrames) return [0, 0, 0];
  const position = Math.max(0, Math.min(maxFrames - 1, framePosition));
  const first = Math.floor(position);
  const second = Math.min(maxFrames - 1, first + 1);
  const amount = position - first;
  return channels.map((samples) => (samples[first] + (samples[second] - samples[first]) * amount) * (2 * Math.PI / 65536));
}

export function buildClipTrackLookup(clip, sourceTrackToBone) {
  const lookup = {};
  const sourceLookup = Object.fromEntries(Object.entries(sourceTrackToBone).map(([name, bone]) => [name.trim().toLocaleLowerCase('en-US'), bone]));
  for (const track of clip.tracks) {
    const targetBone = sourceLookup[track.normalizedName];
    if (targetBone) lookup[targetBone] = track;
  }
  return lookup;
}

export function buildTargetNodeSourceBone(mapping) {
  const result = {};
  for (const [node, chain] of Object.entries(mapping.target_source_chains)) {
    result[node] = chain.length ? chain.at(-1) : null;
  }
  return result;
}

export { IDENTITY, normaliseQuaternion, quaternionMultiply, quaternionInverse, quaternionSlerp, fromWXYZ };
