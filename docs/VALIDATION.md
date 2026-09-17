# Validating a boot

`sudo tools/validate5k.py` checks all of the following and exits non-zero on any failure.
It needs a lit panel (it refuses if the display is in DPMS off) and a logged-in KDE session
for the first check.

| Check | Pass criterion |
|---|---|
| KDE outputs | exactly one enabled output, `eDP-1`, current mode 5120x2880 |
| Timing generator totals | both running OTGs report H total **2720**, V total **2962** |
| Tile frame lock | ten back-to-back `CRTC_STATUS_POSITION` reads: vertical delta, wrapped by V total, **<= 3 lines** every time |
| Per-frame reset idle | `CRTC_TRIGA_CNTL`, `CRTC_TRIGB_CNTL`, `CRTC_FORCE_COUNT_NOW_CNTL` enable bits clear and `CRTC_MASTER_UPDATE_MODE` zero on both OTGs |
| Root link DPCD | lanes 0-3 equalized and symbol-locked (`0x202`/`0x203` = `77 77`), align and sink lock set, tuple `(0x41C, 0x425, 0x4F1)` = `15 00 01` |
| Slave link DPCD | same lane/align/sink status, `0x4F1` = `01` |
| Kernel log | no `link-health recovery`, `FAIL`, `disarmed`, `GSL: Timeout`, `TG counter is not moving`, `dce_transform`, warning or oops |

It also prints, without judging them: the global swap-lock register and the two infoframe
registers it used to corrupt, the memory clock state, GPU power, and every tile bring-up
line from the kernel log.

## Scenarios worth running by hand

1. **Cold boot** — firmware logo straight, panel never stretched at any point, kernel log
   shows the root EDID re-read succeeding with product `AE02` and a peer tile stream created.
2. **Warm reboot** — same, with the TCON already in dual-tile mode.
3. **DPMS off/on**, repeatedly — no link recoveries, no stretched or half-black intermediate.
4. **Suspend / resume** — the right tile must appear in the same frame as the left.
5. **Long idle with screen dimming** — no hang (this is the scenario behind a reported
   hard hang on another machine with this stack).
6. **Fullscreen scaled content** — either the compositor composites, or the image is
   correct across both halves. Never a wrong or black right half.
7. **Thunderbolt DP monitor** — it lights at its own timing, the tiles keep theirs, and
   the kernel log shows no re-pairing of the tile links.
8. **Kernel update** — `imac5k-kmod status` shows the new kernel built and installed before
   you reboot, the previous kernel's module untouched.

## Low-level probes

- `sudo tools/dcedump.py` — the whole DCE 10 display pipeline: surface, viewport,
  watermark, timing-generator and lock registers per pipe, plus the global ones. Diff two
  dumps to see what a modeset changed.
- `sudo tools/genlock_probe.py [a] [b] [seconds]` — scan-out phase between two CRTCs over time.
- `sudo tools/snap.py` — one-shot JSON of both links' DPCD state, hotplug pins and AUX engines.
- `tools/aux.py` — the helper library: raw register access, DPCD reads/writes per link, and
  a context manager that lets AUX run on a link whose hotplug pin is low.
