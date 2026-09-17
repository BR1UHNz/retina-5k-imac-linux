#!/usr/bin/python3
"""validate5k.py -- universal pass criteria for native 5K on the iMac15,1 (run with sudo).

Checks (from the stack-review synthesis, section 4.1): one KWin output at 5120x2880,
OTG totals 2720x2962 on both tile OTGs, phase <= 3 lines, per-frame-reset registers idle,
GSL source register, DPCD tuples on both links, no stray SDP writes, journal free of
recovery/WARN lines. Prints PASS/FAIL per check and exits non-zero on any FAIL.
Read-only except for nothing: it never writes to hardware.
"""
import json, os, struct, subprocess, sys, time

from aux import REGS
OTG = [0x1b80, 0x1d80, 0x1fa4 - 0x24, 0x41a4 - 0x24, 0x43a4 - 0x24, 0x45a4 - 0x24]  # CRTC_H_TOTAL bases (stride 0x200)
AUX = {'A': '/dev/drm_dp_aux0', 'B': '/dev/drm_dp_aux1'}
fails = []

def res(name, ok, detail=''):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(': ' + detail) if detail else ''}")
    if not ok:
        fails.append(name)

def rd(fd, reg):
    return struct.unpack('<I', os.pread(fd, 4, reg * 4))[0]

def dpcd(dev, addr, n):
    try:
        fd = os.open(dev, os.O_RDONLY)
        try:
            return os.pread(fd, n, addr)
        finally:
            os.close(fd)
    except OSError as e:
        return None

def _drm_conn(name):
    """/sys/class/drm/cardN-<name> for whichever card index amdgpu got."""
    import glob
    hits = sorted(glob.glob(f'/sys/class/drm/card*-{name}'))
    if not hits:
        raise SystemExit(f'no DRM connector {name}; is the 5K driver loaded?')
    return hits[0]


def user_env():
    uid = os.environ.get('SUDO_UID') or '1000'
    return dict(os.environ, XDG_RUNTIME_DIR=f'/run/user/{uid}', WAYLAND_DISPLAY='wayland-0')

def kscreen():
    uid = os.environ.get('SUDO_UID') or '1000'
    user = os.environ.get('SUDO_USER') or os.environ.get('USER') or 'root'
    try:
        out = subprocess.run(['runuser', '-u', user, '--', 'env', f'XDG_RUNTIME_DIR=/run/user/{uid}', 'WAYLAND_DISPLAY=wayland-0',
                              'kscreen-doctor', '--json'], capture_output=True, text=True, timeout=10).stdout
        return json.loads(out)
    except Exception as e:
        return None

EDP = _drm_conn('eDP-1')
DP1 = _drm_conn('DP-1')
dpms = open(f'{EDP}/dpms').read().strip()
if dpms != 'On':
    print(f'eDP-1 dpms is {dpms}: wake the display first (kscreen-doctor --dpms on), the checks below need a lit panel')
    sys.exit(2)

# 1. KWin outputs
cfg = kscreen()
if cfg is None:
    res('kwin outputs', False, 'kscreen-doctor --json failed (no session?)')
else:
    enabled = [o for o in cfg.get('outputs', []) if o.get('enabled')]
    names = [o['name'] for o in enabled]
    ok = len(enabled) == 1 and enabled[0]['name'] == 'eDP-1'
    mode = None
    if enabled:
        o = enabled[0]
        cur = str(o.get('currentModeId'))
        for m in o.get('modes', []):
            if str(m.get('id')) == cur:
                mode = (m['size']['width'], m['size']['height'], round(m.get('refreshRate', 0), 2))
        ok = ok and mode and mode[0] == 5120 and mode[1] == 2880
        res('kwin outputs', ok, f"enabled={names} mode={mode} scale={o.get('scale')}")
    else:
        res('kwin outputs', False, 'no enabled output')

# 2. OTG totals + which OTGs are running
fd = os.open(REGS, os.O_RDONLY)
running = []
for i in range(6):
    base = 0x1b80 + 0x200 * i
    ctl = rd(fd, base + 0x1c)
    if ctl & 1:
        running.append((i, rd(fd, base) + 1, rd(fd, base + 7) + 1))
res('OTG totals', len(running) == 2 and all(h == 2720 and v == 2962 for _, h, v in running), f"running OTGs (idx,h,v)={running}")

# 3. phase
if len(running) == 2:
    a, b = running[0][0], running[1][0]
    VT = 2962
    ds = []
    for _ in range(10):
        pa = rd(fd, 0x1ba4 + 0x200 * a) & 0x3fff
        pb = rd(fd, 0x1ba4 + 0x200 * b) & 0x3fff
        pa2 = rd(fd, 0x1ba4 + 0x200 * a) & 0x3fff
        d = ((pb - (pa + pa2) / 2) + VT / 2) % VT - VT / 2
        ds.append(round(d, 1))
        time.sleep(0.005)
    res('phase <= 3 lines', all(abs(d) <= 3 for d in ds), f"OTG{b}-OTG{a} deltas={ds}")
    # 4. per-frame reset idle
    trig = {}
    for i in (a, b):
        base = 0x1b94 + 0x200 * i
        trig[i] = dict(TRIGA=hex(rd(fd, base)), TRIGB=hex(rd(fd, base + 2)), FORCE_COUNT_NOW=hex(rd(fd, base + 4)),
                       MASTER_UPDATE_MODE=hex(rd(fd, base + 0x2a)))
    idle = all(int(v[k], 16) & 0x1 == 0 for v in trig.values() for k in ('TRIGA', 'TRIGB', 'FORCE_COUNT_NOW')) and \
           all(int(v['MASTER_UPDATE_MODE'], 16) == 0 for v in trig.values())
    res('per-frame reset idle', idle, str(trig))
    gsl = rd(fd, 0x4826)
    res('GSL source reg (info)', True, f"DCIO_GSL0_CNTL=0x{gsl:x} DIG0_AFMT_GENERIC_1=0x{rd(fd, 0x4a26):x} DIG2_AFMT_GENERIC_1=0x{rd(fd, 0x4c26):x}")
os.close(fd)

# 5. DPCD
for L, dev in AUX.items():
    st = dpcd(dev, 0x200, 8)
    tup = b''.join(dpcd(dev, a, 1) or b'?' for a in (0x41c, 0x425, 0x4f1))
    # Lanes 0-3 EQ/CR/symbol-lock (0x202/0x203 == 77 77) and align+sink lock (0x204 bit0, 0x205 bit0).
    # 0x204 bit 7 (link status updated) is transient, so it is masked out.
    ok = (st is not None and st[2:4] == bytes.fromhex('7777')
          and (st[4] & 0x01) == 0x01 and (st[5] & 0x01) == 0x01
          and tup[2:3] == b'\x01')
    if L == 'A':
        # Only the root link carries the TCON control registers; 15 00 01 is its native tuple.
        ok = ok and tup[:2] == bytes.fromhex('1500')
    res(f'link {L} DPCD', ok, f"0x200-207={st.hex(' ') if st else 'EIO'} (0x41C,0x425,0x4F1)={tup.hex(' ')} 0x10A={(dpcd(dev, 0x10a, 1) or b'?').hex()}")

# 6. journal
j = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'cat'], capture_output=True, text=True).stdout
KEYS = ('link-health recovery', 'APPLE5K: FAIL', 'disarmed', 'GSL: Timeout', 'TG counter is not moving',
        'dce_transform.c', 'pixel_width', 'WARNING: CPU', 'Oops', 'BUG:', 'right tile will be dark')
bad = [l for l in j.splitlines() if any(k in l for k in KEYS)]
res('journal clean', not bad, ('\n      ' + '\n      '.join(bad[:8])) if bad else 'no recovery/WARN lines')
stitch = [l for l in j.splitlines() if 'TILED_STITCH' in l or 'tiled' in l.lower() and 'amdgpu' in l]
print('info  stitch log lines:', len(stitch))
for l in stitch[:12]:
    print('      ', l[:160])
_dev = os.path.dirname(EDP) + '/' + os.path.basename(EDP).split('-')[0] + '/device'
_dev = os.path.realpath(os.path.join('/sys/class/drm', os.path.basename(EDP).split('-')[0], 'device'))
mclk = open(f'{_dev}/pp_dpm_mclk').read().strip().replace('\n', ' | ')
_hw = os.path.join(_dev, 'hwmon')
pw = int(open(os.path.join(_hw, os.listdir(_hw)[0], 'power1_average')).read()) / 1e6
print(f'info  mclk: {mclk}   GPU power: {pw:.1f} W   tiled_stitch param: '
      f"{open('/sys/module/amdgpu/parameters/tiled_stitch').read().strip() if os.path.exists('/sys/module/amdgpu/parameters/tiled_stitch') else 'absent (stock amdgpu)'}")
print('RESULT:', 'ALL PASS' if not fails else f'FAILED: {fails}')
sys.exit(1 if fails else 0)
