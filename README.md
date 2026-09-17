# Native 5120x2880 on the Late-2014 Retina 5K iMac under Linux

This is a working, self-maintaining native-5K display stack for the **iMac15,1**
(Late 2014 27" Retina 5K, Radeon R9 M295X "Tonga XT", `1002:6938` / `106b:013a`,
amdgpu **DCE 10.0**) on Fedora 44 with KDE Plasma Wayland.

The panel comes up as **one 5120x2880 output**, frame-locked, with the memory clock
free to idle. A kernel update rebuilds the driver by itself.

> **Status:** confirmed working on real hardware (2026-09-16). Before this, pronkin's
> compatibility matrix listed iMac15,1 5K as *Untested* and the only other data point
> for this GPU ran the panel as two separate monitors on kernel 7.0.1.

---

## Why the panel needs a driver at all

The 27" Retina 5K panel is a **2x1 tiled display** behind a Parade DP665 timing
controller. It is fed by two internal DisplayPort links:

| Link | Connector | Transmitter | HPD | AUX | Shows |
|---|---|---|---|---|---|
| A (root) | `eDP-1` | UNIPHY D | HPD2 | engine 1 | left tile, 2560x2880 |
| B (slave) | `DP-1` | UNIPHY C | HPD1 | engine 0 | right tile, 2560x2880 |

`DP-2` / `DP-3` are the Thunderbolt 2 ports and are untouched by any of this.

Apple's firmware leaves the timing controller in a **single-link 4K compatibility
mode** whenever a non-Apple EFI binary (GRUB) boots: the root link reports EDID
product `APP AE01` with a 3840x2160 preferred mode, the second link's receiver is
off and its hotplug line stays low. Linux therefore sees one 4K panel.

Writing **`1` to vendor DPCD register `0x4F1` on the root link** wakes the second
tile. About 4 ms later its hotplug line rises, the link trains at HBR2 x4, and the
root EDID flips to `APP AE02` carrying a DisplayID tile block. The latch is volatile:
putting the root link into D3 (any DPMS off) clears it, so it has to be re-asserted
on every power-up.

A single 5120x2880 stream is impossible on this hardware, so the two tiles are driven
as two streams from one CRTC and presented to userspace as one display.

Full register-level detail: [docs/HARDWARE.md](docs/HARDWARE.md).

---

## What is in here

```
patches/community/   the upstream community stack this builds on (12 patches)
patches/fixes/        the fixes added here (8 patches)
install/             the per-kernel auto-rebuild pipeline
tools/               hardware validation and low-level probes
dumps/               EDIDs and measured DPCD state from real hardware
docs/                hardware notes, the generic amdgpu bugs, validation criteria
```

### The fixes added here

| Patch | What it fixes |
|---|---|
| `13-dce-genlock` | `DCIO_GSL0_CNTL` is one global register but was written through a per-CRTC macro, landing in another output's infoframe memory; the per-frame CRTC reset can never arm on DCE < 12, so it is gated off and replaced with a measured re-align |
| `14-stitch-gate` | the internal panel could end up with **zero** modes (black screen, no console) whenever the tile pairing was not yet complete; adds a real "can we stitch right now" predicate with fallback and hysteresis, a retrying EDID re-read, right-tile re-attach on hotplug, and a DRM-lease guard |
| `15-stitch-planes` | rejects window layouts the two tiles cannot show (the suspected cause of a reported hard hang), attaches the right tile on every commit rather than only on page flips, refreshes the second tile's buffer address, and refuses tearing flips |
| `16-link-lifecycle` | stops the panel re-pairing itself to a Thunderbolt monitor, makes the wake idempotent, moves the wake into the root link's own power-up, widens the second tile's AUX wait to match measured hardware timing, hands the panel back to firmware from the root at shutdown, and replaces a half-second display power cycle under lock with a compositor-driven modeset |
| `17` / `18` | GPU-reset hardening, from ahmadtv (drm/amd#5810) |
| `19-dce10-pplib-in-sync` | DCE 10 never told PowerPlay the displays were timing-synchronized, so the memory clock was pinned at maximum with both tiles lit: about **48 W at idle instead of 17 W**, and 83 C |
| `20-fixups-1` | bounds the recovery escalation per boot; fixes an EDID swap outside its lock |

Several of these are **generic amdgpu bugs**, not Apple-specific — see
[docs/UPSTREAM-BUGS.md](docs/UPSTREAM-BUGS.md).

---

## Installing

**This builds and installs an out-of-tree `amdgpu`. Read `install/deploy.sh` first.**
It is written for this exact machine and for Fedora. It does not touch the GRUB
default or the kernel command line, and a kernel that fails to reach a working
desktop twice puts itself back on the stock driver.

```sh
git clone https://github.com/br1uhnz/retina-5k-imac-linux
cd imac15-1-native-5k/install
./mkstack.sh                # assemble the patch stack for the 7.2 kernel series
sudo ./deploy.sh            # install tooling, build and install for every kernel
```

The first build takes about six minutes. A desktop notice appears when it is safe
to restart. Then reboot.

```sh
imac5k-kmod status                  # per-kernel state
sudo ./tools/validate5k.py          # full hardware pass criteria
sudo ./deploy.sh --remove           # back to the stock driver everywhere
```

**If a patched kernel ever black-screens:** power-cycle twice and it reverts itself;
or pick the previous kernel in GRUB; or add
`modprobe.blacklist=amdgpu rd.driver.blacklist=amdgpu` to the boot entry and run
`sudo imac5k-kmod revert $(uname -r)`.

---

## Verified on hardware

| Check | Result |
|---|---|
| KDE outputs | one, `eDP-1`, 5120x2880 @ 59.98 Hz |
| Both tile timing generators | 2720x2962 total each |
| Tile frame lock | 0-1 scan lines apart, 0.0 ppm |
| Root link DPCD `(0x41C, 0x425, 0x4F1)` | `15 00 01` (native); `05 02 00` in compat mode |
| Sink status `0x205` | `01` on both links |
| Memory clock at idle | 143 MHz, 17.4 W (was pinned at 1362 MHz, 48 W) |
| Kernel log | no link recoveries, no sync timeouts, no warnings |

Reproduce with `sudo tools/validate5k.py`; criteria in [docs/VALIDATION.md](docs/VALIDATION.md).

---

## Credits

This stands on a lot of other people's reverse engineering:

- **[MarkPronkin/imac5k-universal-linux-patcher](https://github.com/MarkPronkin/imac5k-universal-linux-patcher)** — the lean core and tile-stitch layer that `patches/community/` comes from.
- **ahmadtv** — lean core for the 7.2 series and the GPU-reset patches.
- **taprobane99** — slim patch for 7.3-rc1.
- **[mcirsta/linux-imac-5k](https://github.com/mcirsta/linux-imac-5k)** — the original iMac 5K work; PR #4 is the only other iMac15,1 + Tonga data point.
- **[freedesktop.org drm/amd issue #4455](https://gitlab.freedesktop.org/drm/amd/-/issues/4455)** — the long-running community thread.

`patches/community/` is redistributed unmodified under GPL-2.0, in the order the
upstream project applies it. The work in `patches/fixes/`, `install/` and `tools/` is
new here.

## Licence

GPL-2.0, matching the Linux kernel. See [LICENSE](LICENSE).
