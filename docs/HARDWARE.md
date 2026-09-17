# iMac15,1 Retina 5K panel — hardware notes

Everything here was measured on a real iMac15,1 (R9 M295X, Fedora 44, kernel
7.2.5-200.fc44), not inferred. Register offsets are **dword indices** as used by
`/sys/kernel/debug/dri/*/amdgpu_regs` (file offset = index x 4).

## Panel and links

2x1 tiled panel behind a **Parade DP665** timing controller (TCON).

- DPCD sink OUI `00-10-FA`, device id `MN27f1`, HW rev 1.0, FW 10.8
- DPCD 1.2, HBR2 x4, TPS3, enhanced framing
- `0x00D` (eDP configuration cap) = `00` on **both** links — no alternate scrambler reset advertised
- `0x246` = `0x20` (TEST_CRC supported)
- No PSR (`0x070` = 0)

| | Link A (root) | Link B (slave) |
|---|---|---|
| DRM connector | `eDP-1` | `DP-1` |
| Transmitter | UNIPHY D (`INTERNAL_UNIPHY1` enum 2) | UNIPHY C (`UNIPHY1` enum 1) |
| Hotplug | HPD2, status reg `0x18a0` | HPD1, status reg `0x1898` |
| AUX engine | 1 (`AUX_CONTROL` `0x5c1c`) | 0 (`AUX_CONTROL` `0x5c00`) |
| Device node | `/dev/drm_dp_aux0` | `/dev/drm_dp_aux1` |
| I2C | `aux hw bus 0` | `aux hw bus 1` |
| Tile | (0,0) left | (1,0) right |

`DP-2` (UNIPHY A, HPD3, AUX 2) and `DP-3` (UNIPHY B, HPD4, AUX 3) are the Thunderbolt 2
ports. HPD5/6 and AUX 4/5 are unused.

## The two modes of the TCON

**Compatibility mode** (what Apple's firmware leaves behind for a non-Apple bootloader):

- Link A EDID product `APP AE01`, preferred 3840x2160
- HPD1 low, link B receiver off, clock recovery fails on every lane
- Link A tuple `(0x41C, 0x425, 0x4F1)` = `05 02 00`

**Native dual-tile mode**, entered by writing `1` to vendor DPCD **`0x4F1` on link A**
(this is the Windows Boot Camp driver's "opcode 1265"):

- HPD1 rises ~4 ms later and stays high; `DP-1` then detects normally
- Link B trains HBR2 x4: `0x200`-`0x205` = `01 00 77 77 01 01`
- Link A EDID flips to `APP AE02` with a DisplayID tile block, tile (0,0), caps `0x82`
- Link B EDID is `AE02`, tile (1,0), caps `0x80`; tiled product `AE03`, serial 258087541
- Link A tuple `(0x41C, 0x425, 0x4F1)` = `15 00 01`
- Sink status `0x205` bit 0 is set on **both** links

**The latch is volatile.** Putting link A into D3 — any DPMS off — clears `0x4F1` by
itself and HPD1 drops with it. It must be re-asserted every time the root link powers up.
(This differs from the iMac18,3 captures, where explicit clears were needed.)

## Timing

Per tile: **2560x2880 @ 59.98158 Hz**, 483.25 MHz, H 48/32/80 (+hsync),
V 3/10/69 (-vsync), totals **2720x2962**. CRTC registers hold total-1: `0xa9f` / `0xb91`.

Both tiles share one DP clock source: measured **0.0 ppm**, phase within 0-1 scan lines
once aligned.

Apple's own merged EDID (from `AppleGraphicsDevicePolicy`) describes the panel as a single
DisplayID Type I timing: 5120x2880 @ 59.992864, 938.25 MHz, H 48/32/80, V 3/5/74 — i.e.
half the horizontal blanking per tile that the tile EDIDs advertise. Driving that timing
instead works but changes nothing visible.

A single 5120x2880 stream is **not possible**: 938.25 MHz exceeds the DCE 10 display-clock
cap of 625 MHz and the 17.28 Gbps link budget.

## Useful register offsets (DCE 10, per-CRTC stride 0x200)

| Register | OTG0 |
|---|---|
| `CRTC_H_TOTAL` | `0x1b80` |
| `CRTC_V_TOTAL` | `0x1b87` |
| `CRTC_STATUS_POSITION` | `0x1ba4` |
| `CRTC_TRIGA_CNTL` | `0x1b94` |
| `CRTC_TRIGB_CNTL` | `0x1b96` |
| `CRTC_FORCE_COUNT_NOW_CNTL` | `0x1b98` |
| `CRTC_CONTROL` | `0x1b9c` |
| `CRTC_MASTER_UPDATE_MODE` | `0x1bbe` |
| `GRPH_PRIMARY_SURFACE_ADDRESS` | `0x1a04` |
| `GRPH_X_START` / `GRPH_X_END` | `0x1a0b` / `0x1a0d` |
| `VIEWPORT_START` / `VIEWPORT_SIZE` | `0x1b5c` / `0x1b5d` |
| `DPG_PIPE_URGENCY_CONTROL` | `0x1b33` |
| `DPG_PIPE_STUTTER_CONTROL` | `0x1b35` |

Global: `DCIO_GSL0_CNTL` `0x4826`, `MASTER_UPDATE_LOCK` `0x1bbd`,
`DMIF_STATUS` `0x2f7` (bit 28 = underflow, latched, write-1-to-clear),
`DIG0_AFMT_GENERIC_1` `0x4a26`, `DIG2_AFMT_GENERIC_1` `0x4c26`.

With the stitch active, **`DP-1` is on OTG0 and `eDP-1` on OTG1** — the reverse of the
stock layout. Any measurement that assumes "OTG0 is the internal panel" will be wrong.

## Vendor behaviour, from Apple's macOS driver

`AMD9000Controller.kext` (matches `0x69381002`) contains `syncCrtcToCrtc(master, slave)`:

- returns unless both CRTCs have `MASTER_EN` set
- writes **absolute MMIO `0x12098`** (= dword `0x4826`, `DCIO_GSL0_CNTL`) with the master CRTC index
- arms the slave's `CRTC_TRIGA_CNTL` with source `0x10` (`GSL_GROUP0`), edge from `V_SYNC_A_POL`
- sets `FORCE_COUNT_NOW_MODE = 2`, polls `OCCURRED` up to 80000 x `IODelay(1)`
- then zeroes all three registers
- **never touches `DCP_GSL_CONTROL`**

This is what confirms `DCIO_GSL0_CNTL` is a single global register — see
[UPSTREAM-BUGS.md](UPSTREAM-BUGS.md) bug 1.

`setMasterLock(crtc, lock)` ORs in the shared-surface mask and locks every CRTC sharing
that surface, i.e. Apple uses a **grouped** update lock for tiles.

`AppleGraphicsDevicePolicy` ConfigMap `Mac-42FD25EABCABB274` maps to `Config2`
(`GFX0`: EDID index 0, FeatureControl 12, unload false).

## Pitfalls worth knowing

- **eDP native-timing trap.** amdgpu keeps the eDP cached native (EDID-preferred) timing
  and scales to it when the refresh rate matches, so an eDP connector "set to 2560x2880"
  can still scan out 4K timing. DC also caches the eDP sink and eDP has no hotplug IRQ.
  Force a re-read with debugfs `eDP-1/trigger_hotplug` 0 then 1. Always confirm the real
  timing from `CRTC_H_TOTAL` / `CRTC_V_TOTAL`, never from DRM state. This is structurally
  impossible once the tiles are stitched, which is one reason to stitch.
- A forced-on DRM connector becomes a `SIGNAL_TYPE_VIRTUAL` sink and produces no output.
- debugfs `edid_override` reset needs exactly five bytes: `printf reset > ...`
  (`echo` adds a newline and gives `EINVAL`).
- DCE AUX engines abort every transaction while their hotplug pin is low
  (`AUX_SW_HPD_DISCON`). Set `AUX_CONTROL` bit 16 (`AUX_IGNORE_HPD_DISCON`) to talk to a
  link whose HPD is down.
- A KDE DPMS off leaves the TCON's AUX alive (`DIGON` and `ENA_BL` go low); it is not a
  panel power cycle.
- An **unprivileged `lsinitrd` silently prints nothing**. This machine's host-only
  initramfs really does contain `amdgpu` plus ~690 firmware files; check with `sudo`.
