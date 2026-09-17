#!/usr/bin/env python3
"""Root-only one-shot telemetry snapshot of both iMac panel links (JSON on stdout)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aux import Regs, dpcd_read, hpd_ignored

out = {'t': time.time()}
r = Regs()
out['hpd_sense'] = [(r.rd(0x1898 + 8 * i) >> 1) & 1 for i in range(6)]      # DC_HPD1..6
out['hpd_int_status'] = [f"{r.rd(0x1898 + 8 * i):08x}" for i in range(6)]
out['aux_control'] = [f"{r.rd(0x5c00 + 0x1c * i):08x}" for i in range(2)]
r.close()


def grab(link):
    d = {}
    for name, (addr, n) in {'lnk': (0x100, 2), 'status': (0x200, 6), 'power': (0x600, 1),
                            'vendor': (0x40c, 0x24), 'esi': (0x2000, 6)}.items():
        b, err = dpcd_read(link, addr, n)
        d[name] = b.hex(' ') + (f' ERR:{err}' if err else '')
    return d


out['A'] = grab('A')
with hpd_ignored('B'):
    out['B'] = grab('B')
conn = {}
for c in ('eDP-1', 'DP-1', 'DP-2', 'DP-3'):
    p = f'/sys/class/drm/card1-{c}/status'
    conn[c] = open(p).read().strip() if os.path.exists(p) else '?'
out['drm'] = conn
print(json.dumps(out))
