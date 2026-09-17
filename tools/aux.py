#!/usr/bin/env python3
"""Low-level helpers for poking the iMac15,1 panel links through amdgpu.

Link A = eDP-1  -> /dev/drm_dp_aux0, AUX engine 1, HPD2, i2c "aux hw bus 0"
Link B = DP-1   -> /dev/drm_dp_aux1, AUX engine 0, HPD1, i2c "aux hw bus 1"

DCE AUX engines abort every transaction while their HPD pin is low
(AUX_SW_HPD_DISCON).  Link B's HPD is never asserted by the TCON, so for link B
we temporarily set AUX_CONTROL.AUX_IGNORE_HPD_DISCON.
"""
import contextlib, errno, fcntl, os, struct, time

def _find_regs():
    """The amdgpu card's debugfs register window (the index is not always 1)."""
    import glob
    hits = sorted(glob.glob('/sys/kernel/debug/dri/*/amdgpu_regs'))
    if not hits:
        raise SystemExit('no amdgpu_regs in debugfs: run as root, with amdgpu loaded')
    return hits[0]

REGS = _find_regs()
AUX_CONTROL = lambda eng: 0x5c00 + 0x1c * eng
AUX_SW_STATUS = lambda eng: 0x5c04 + 0x1c * eng
IGNORE_HPD_DISCON = 1 << 16
LINKS = {'A': dict(aux='/dev/drm_dp_aux0', engine=1, hpd=1),
         'B': dict(aux='/dev/drm_dp_aux1', engine=0, hpd=0)}


def _find_i2c(name):
    for d in sorted(os.listdir('/sys/bus/i2c/devices')):
        p = f'/sys/bus/i2c/devices/{d}/name'
        if d.startswith('i2c-') and os.path.exists(p) and open(p).read().strip() == name:
            return '/dev/' + d
    return None


LINKS['A']['i2c'] = _find_i2c('AMDGPU DM aux hw bus 0')
LINKS['B']['i2c'] = _find_i2c('AMDGPU DM aux hw bus 1')


class Regs:
    def __init__(self):
        self.fd = os.open(REGS, os.O_RDWR)

    def rd(self, reg):
        return struct.unpack('<I', os.pread(self.fd, 4, reg * 4))[0]

    def wr(self, reg, val):
        os.pwrite(self.fd, struct.pack('<I', val), reg * 4)

    def close(self):
        os.close(self.fd)


@contextlib.contextmanager
def hpd_ignored(link='B'):
    """Let AUX run on the given link although its HPD pin is low."""
    r = Regs()
    reg = AUX_CONTROL(LINKS[link]['engine'])
    old = r.rd(reg)
    r.wr(reg, old | IGNORE_HPD_DISCON)
    try:
        yield r
    finally:
        r.wr(reg, old)
        r.close()


def dpcd_read(link, addr, n):
    fd = os.open(LINKS[link]['aux'], os.O_RDONLY)
    try:
        out = bytearray()
        while len(out) < n:
            chunk = min(16, n - len(out))
            try:
                b = os.pread(fd, chunk, addr + len(out))
            except OSError as e:
                return bytes(out), errno.errorcode.get(e.errno, str(e.errno))
            if not b:
                return bytes(out), 'short'
            out += b
        return bytes(out), None
    finally:
        os.close(fd)


def dpcd_write(link, addr, data):
    fd = os.open(LINKS[link]['aux'], os.O_WRONLY)
    try:
        return os.pwrite(fd, bytes(data), addr)
    finally:
        os.close(fd)


I2C_SLAVE = 0x0703


def i2c_read(link, addr7, n, offset=None):
    fd = os.open(LINKS[link]['i2c'], os.O_RDWR)
    try:
        fcntl.ioctl(fd, I2C_SLAVE, addr7)
        if offset is not None:
            os.write(fd, bytes([offset]))
        out = bytearray()
        while len(out) < n:
            out += os.read(fd, min(16, n - len(out)))
        return bytes(out)
    finally:
        os.close(fd)


def hexdump(base, data, width=16):
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        lines.append(f"{base + i:06x}: {chunk.hex(' '):<{width*3}} {''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)}")
    return '\n'.join(lines)
