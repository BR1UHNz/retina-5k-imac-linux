#!/usr/bin/env python3
"""Measure scanout phase between the two active CRTCs (root). Prints the vertical
line offset (B - A, modulo vtotal) over time; a constant small value = genlocked."""
import os, struct, sys, time, statistics
VT = 2962
REG = [0x1ba4, 0x1da4, 0x1fa4, 0x41a4, 0x43a4, 0x45a4]
import glob
_regs = sorted(glob.glob('/sys/kernel/debug/dri/*/amdgpu_regs'))
if not _regs:
    raise SystemExit('no amdgpu_regs in debugfs: run as root, with amdgpu loaded')
fd = os.open(_regs[0], os.O_RDONLY)
def pos(i):
    v = struct.unpack('<I', os.pread(fd, 4, REG[i] * 4))[0]
    return v & 0x3fff, (v >> 16) & 0x3fff
a, b = int(sys.argv[1]) if len(sys.argv) > 1 else 0, int(sys.argv[2]) if len(sys.argv) > 2 else 1
secs = float(sys.argv[3]) if len(sys.argv) > 3 else 5
out = []
t0 = time.time()
while time.time() - t0 < secs:
    va, ha = pos(a); vb, hb = pos(b); va2, _ = pos(a)
    d = ((vb - (va + va2) / 2) + VT / 2) % VT - VT / 2
    out.append((time.time() - t0, d))
    time.sleep(0.05)
ds = [d for _, d in out]
print(f"crtc{a} vs crtc{b}: samples={len(ds)} offset lines: min={min(ds):.1f} max={max(ds):.1f} median={statistics.median(ds):.1f} stdev={statistics.pstdev(ds):.2f}")
print("first/last:", [round(d, 1) for _, d in out[:5]], [round(d, 1) for _, d in out[-5:]])
