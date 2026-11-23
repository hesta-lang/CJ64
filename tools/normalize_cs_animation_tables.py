#!/usr/bin/env python3
"""Calibrate GTA SA animation channels for the CS CJ 20-node DynOS actor."""
from __future__ import annotations
import argparse, json, math, re
from pathlib import Path

REGISTER_RE = re.compile(
    r'(smlua_anim_util_register_animation\("([^"]+)",\s*(.*?),\s*\n\s*\{\s*)'
    r'(.*?)'
    r'(\n\s*\},\s*\{\s*)'
    r'(.*?)'
    r'(\n\s*\}\s*\))', re.S
)

def qnorm(q):
    n = math.sqrt(sum(x*x for x in q))
    if n < 1e-12: raise ValueError("zero-length quaternion")
    return tuple(x/n for x in q)

def qmul(a,b):
    ax,ay,az,aw=a; bx,by,bz,bw=b
    return (aw*bx+ax*bw+ay*bz-az*by,
            aw*by-ax*bz+ay*bw+az*bx,
            aw*bz+ax*by-ay*bx+az*bw,
            aw*bw-ax*bx-ay*by-az*bz)

def qinv(q):
    x,y,z,w=qnorm(q)
    return (-x,-y,-z,w)

def q_from_euler_xyz(rx,ry,rz):
    cr,sr=math.cos(rx/2),math.sin(rx/2)
    cp,sp=math.cos(ry/2),math.sin(ry/2)
    cy,sy=math.cos(rz/2),math.sin(rz/2)
    return qnorm((sr*cp*cy-cr*sp*sy,
                  cr*sp*cy+sr*cp*sy,
                  cr*cp*sy-sr*sp*cy,
                  cr*cp*cy+sr*sp*sy))

def euler_xyz(q):
    x,y,z,w=qnorm(q)
    rx=math.atan2(2*(w*x+y*z),1-2*(x*x+y*y))
    sy=2*(w*y-z*x)
    ry=math.copysign(math.pi/2,sy) if abs(sy)>=1 else math.asin(sy)
    rz=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
    return rx,ry,rz

def signed16(v): return v-65536 if v>=32768 else v
def decode_angle(v): return signed16(v)*(2*math.pi/65536)
def encode_angle(v): return int(round(v*65536/(2*math.pi)))&0xFFFF
def parse_values(block): return [int(x,16) for x in re.findall(r"0x([0-9A-Fa-f]{4})",block)]

def channel(values,indices,index):
    n,off=indices[2*index:2*index+2]
    return n,off,values[off:off+n]

def format_values(values):
    return "\n"+"\n".join("        "+", ".join(f"0x{x:04X}" for x in values[i:i+12])+","
                          for i in range(0,len(values),12))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path,help="private generated animation Lua module")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--reference",default="cj64_anim_idle")
    parser.add_argument("--nodes",type=int,default=20)
    args=parser.parse_args()
    text=args.source.read_text(encoding="utf-8")
    matches=list(REGISTER_RE.finditer(text))
    if not matches: raise SystemExit("No animation registrations found")
    names=[m.group(2) for m in matches]
    if len(names)!=len(set(names)): raise SystemExit("Duplicate animation registration names")
    reference=next((m for m in matches if m.group(2)==args.reference),None)
    if reference is None: raise SystemExit(f"Reference animation not found: {args.reference}")
    expected_channels=3+args.nodes*3
    ref_values=parse_values(reference.group(4))
    ref_indices=parse_values(reference.group(6))
    if len(ref_indices)!=expected_channels*2:
        raise SystemExit(f"Reference has {len(ref_indices)//2} channels; expected {expected_channels}")
    bases=[]
    for node in range(args.nodes):
        angles=[]
        for axis in range(3):
            count,off,samples=channel(ref_values,ref_indices,3+node*3+axis)
            if count<1 or len(samples)!=count: raise SystemExit("Invalid reference channel length")
            angles.append(decode_angle(samples[0]))
        bases.append(q_from_euler_xyz(*angles))

    replacements=[]; reports=[]
    for match in matches:
        values=parse_values(match.group(4))
        indices=parse_values(match.group(6))
        if len(indices)!=expected_channels*2:
            raise SystemExit(f"{match.group(2)} has incompatible channel count")
        out=list(values)
        for node,base in enumerate(bases):
            counts=[]; arrays=[]
            for axis in range(3):
                count,off,samples=channel(values,indices,3+node*3+axis)
                counts.append(count); arrays.append([decode_angle(x) for x in samples])
            if len(set(counts))!=1 or counts[0]<1:
                raise SystemExit(f"{match.group(2)} node {node} has inconsistent channels")
            inv_base=qinv(base)
            frames=[]
            for f in range(counts[0]):
                q=q_from_euler_xyz(arrays[0][f],arrays[1][f],arrays[2][f])
                frames.append(euler_xyz(qmul(inv_base,q)))
            for axis in range(3):
                for f in range(1,len(frames)):
                    cur=frames[f][axis]; prev=frames[f-1][axis]
                    while cur-prev>math.pi: cur-=2*math.pi
                    while cur-prev<-math.pi: cur+=2*math.pi
                    row=list(frames[f]); row[axis]=cur; frames[f]=tuple(row)
                count,off,_=channel(values,indices,3+node*3+axis)
                for f in range(count): out[off+f]=encode_angle(frames[f][axis])
        replacements.append((match.span(4),format_values(out)))
        reports.append({"name":match.group(2),"channels":len(indices)//2,
                        "values_entries":len(out),"samples":ref_indices[6]})
    for (start,end),replacement in reversed(replacements):
        text=text[:start]+replacement+text[end:]
    text=text.replace(
        "-- CJ64: first-pass GTA San Andreas ped.ifp retarget for SM64CoopDX.",
        "-- CJ64: GTA San Andreas animation tables calibrated for the CS CJ DynOS actor.")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(text,encoding="utf-8")
    report={"format":"cj64-cs-animation-calibration-report-v1",
            "source_module":args.source.name,"reference_animation":args.reference,
            "target_node_count":args.nodes,
            "normalization":"inverse(reference quaternion) * sample quaternion",
            "source_ifp":"not included","visual_validation":False,"in_game_validation":False,
            "clips":reports,
            "limitations":["The CS actor has 20 animated parts, not the full GTA skeleton.",
                "Independent finger, toe, breast and belly tracks cannot be represented one-to-one.",
                "This is an experimental best-fit conversion, not perfect GTA SA animation parity."]}
    args.output.with_suffix(".report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(args.output),"animations":len(reports),"nodes":args.nodes},indent=2))

if __name__=="__main__": main()
