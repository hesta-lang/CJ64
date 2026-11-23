#!/usr/bin/env python3
"""Parent-aware rotation retargeting for GTA SA IFP poses to SM64 Mario nodes.

IFP channels are local bone rotations. Retargeting them as if their source and
destination bones had identical parents loses the motion of any source parent
that is absent from the destination hierarchy. This module reconstructs source
global pose deltas from source rest transforms, then solves each destination
node's local rotation against its actual animated destination parent.
"""
from __future__ import annotations

import math

IDENTITY = (0.0, 0.0, 0.0, 1.0)


def qnorm(q):
    length = math.sqrt(sum(float(v) * float(v) for v in q))
    if not math.isfinite(length) or length < 1e-12:
        raise ValueError("zero-length or invalid quaternion")
    return tuple(float(v) / length for v in q)


def qmul(a, b):
    ax, ay, az, aw = qnorm(a)
    bx, by, bz, bw = qnorm(b)
    return qnorm((
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ))


def qinv(q):
    x, y, z, w = qnorm(q)
    return (-x, -y, -z, w)


def q_from_axis_angle(axis, radians):
    length = math.sqrt(sum(float(v) * float(v) for v in axis))
    if length < 1e-12:
        raise ValueError("rotation axis must be non-zero")
    half = radians * 0.5
    scale = math.sin(half) / length
    return qnorm((axis[0] * scale, axis[1] * scale, axis[2] * scale, math.cos(half)))


def _source_order(source_parent_by_bone, source_rest_global, root_bone):
    if root_bone not in source_rest_global:
        raise ValueError(f"source root {root_bone!r} has no rest transform")
    order = []
    visiting = set()
    visited = set()

    def visit(name):
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"cycle in source bone hierarchy at {name!r}")
        if name not in source_rest_global:
            raise ValueError(f"source bone {name!r} has no rest transform")
        visiting.add(name)
        parent = source_parent_by_bone.get(name)
        if parent is not None:
            if parent not in source_rest_global:
                raise ValueError(f"source parent {parent!r} of {name!r} has no rest transform")
            visit(parent)
        visiting.remove(name)
        visited.add(name)
        order.append(name)

    for name in source_rest_global:
        visit(name)
    if source_parent_by_bone.get(root_bone) is not None:
        raise ValueError("the configured source root must not have a parent")
    return order


def build_source_global_deltas(
    source_parent_by_bone,
    source_rest_global,
    source_pose_local,
    *,
    root_bone,
):
    """Return each source bone's global rotation delta from its bind pose.

    source_rest_global and source_pose_local use XYZW quaternions. A missing
    IFP track means identity local pose delta. The source root's IFP Normal
    channel is intentionally excluded; SM64CoopDX owns player/world
    orientation and Mario Body must stay identity.
    """
    rest = {name: qnorm(value) for name, value in source_rest_global.items()}
    parents = dict(source_parent_by_bone)
    order = _source_order(parents, rest, root_bone)
    current_global = {}
    deltas = {}

    for name in order:
        parent = parents.get(name)
        if name == root_bone or parent is None:
            # The configured GTA root is deliberately static. Any unrelated
            # disconnected helper root is also held at bind pose.
            current_global[name] = rest[name]
            deltas[name] = IDENTITY
            continue

        local_rest = qmul(qinv(rest[parent]), rest[name])
        pose_delta = qnorm(source_pose_local.get(name, IDENTITY))
        current_global[name] = qmul(
            qmul(current_global[parent], local_rest),
            pose_delta,
        )
        deltas[name] = qmul(current_global[name], qinv(rest[name]))

    return deltas


def retarget_global_deltas_to_mario(
    target_nodes,
    target_parent_animation_node,
    target_parent_rest_rotation,
    target_node_source_bone,
    source_global_deltas,
    axis_align,
    *,
    root_node="Body",
):
    """Solve Mario local animation channels from source global pose deltas.

    For each destination node, calculate the source bone's global delta and
    express it relative to the current global delta of the destination's
    animated parent. target_parent_rest_rotation[node] is the rest-space
    orientation of the node's actual immediate parent (including static
    helper nodes between animated parts), in target armature space.

    This explicitly handles hierarchy differences such as GTA's clavicle
    being parented to Neck while Mario's arm animated part is parented to
    Torso. Returns (local_channels, reconstructed_target_global_deltas).
    """
    align = qnorm(axis_align)
    align_inv = qinv(align)
    local_channels = {}
    target_global = {}

    for node in target_nodes:
        if node == root_node:
            local_channels[node] = IDENTITY
            target_global[node] = IDENTITY
            continue

        parent_node = target_parent_animation_node.get(node)
        if parent_node is not None and parent_node not in target_global:
            raise ValueError(
                f"destination parent {parent_node!r} of {node!r} "
                "must appear earlier in target_nodes"
            )
        parent_delta = target_global.get(parent_node, IDENTITY)
        parent_rest = qnorm(target_parent_rest_rotation.get(node, IDENTITY))
        source_bone = target_node_source_bone.get(node)

        if source_bone is None:
            local_channels[node] = IDENTITY
            target_global[node] = parent_delta
            continue

        if source_bone not in source_global_deltas:
            raise ValueError(
                f"destination node {node!r} refers to missing source bone {source_bone!r}"
            )
        source_delta = qnorm(source_global_deltas[source_bone])
        desired_global = qmul(qmul(align, source_delta), align_inv)

        # D_child = D_parent * T_parent_rest * Q_child * inv(T_parent_rest)
        # Solve Q_child for the source's desired global pose. This includes
        # parent motion omitted from the target hierarchy.
        local = qmul(
            qmul(
                qmul(qinv(parent_rest), qinv(parent_delta)),
                desired_global,
            ),
            parent_rest,
        )
        local_channels[node] = qnorm(local)
        target_global[node] = qmul(
            qmul(
                qmul(parent_delta, parent_rest),
                local_channels[node],
            ),
            qinv(parent_rest),
        )

    return local_channels, target_global
