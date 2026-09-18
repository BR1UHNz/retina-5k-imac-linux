# Generic amdgpu bugs found while doing this

These are defects in stock `drivers/gpu/drm/amd` as of **Linux 7.2.5**. None of them
need Apple hardware to reproduce; they affect any DCE 6/8/10/11.x (and, for the last
one, DCE 12) board. They are listed here because they were found while making the
iMac 5K panel work, and because fixes for the first three are in `patches/fixes/`.

**Upstream status.** Bugs 1 and 6 are reported together as [drm/amd issue
#5858](https://gitlab.freedesktop.org/drm/amd/-/issues/5858), open since 2026-09-17.
The other four have not been reported: 2 and 3 are gated off here rather than repaired,
4 is worked around instead of fixed, and 5 needs DCE 12 hardware to confirm.
Signed-off-by patches for 1 and 6 exist and can go to amd-gfx if a maintainer asks.

---

## 1. `DCIO_GSL0_CNTL` is written at a per-CRTC offset

`dce110_timing_generator_setup_global_swap_lock()` does:

```c
dm_write_reg(tg->ctx, CRTC_REG(mmDCIO_GSL0_CNTL), value);
```

`CRTC_REG()` adds `tg110->offsets.crtc`, which is `0x200` per timing-generator instance.
But `DCIO_GSL0_CNTL` (dword `0x4826` on DCE 10 and 11.x) is **one global DCIO register**,
not a per-CRTC one, and this is its only writer in all of `dc/`.

Two consequences:

1. The global swap lock's vsync source is only ever programmed when the sync group
   happens to include TG0. With any other group membership the slave CRTC locks to
   whatever the stale `VSYNC_SEL` selects.
2. The TG1 write lands on `mmDIG0_AFMT_GENERIC_1` (`0x4a26`) and the TG2 write on
   `mmDIG2_AFMT_GENERIC_1` (`0x4c26`) — **another display output's infoframe/SDP payload
   memory** — on every `dc_trigger_sync()`.

Confirmed against AMD's own shipping macOS driver for this GPU, which writes the register
at its absolute address with the master CRTC index as the value (see
[HARDWARE.md](HARDWARE.md)).

DCE 11.2 uses the same address. An upstream fix needs `0x1924` for DCE 6/8.

Fix: `patches/fixes/13-dce-genlock.patch`. Reported upstream: [drm/amd#5858](https://gitlab.freedesktop.org/drm/amd/-/issues/5858).

---

## 2. The per-frame CRTC position reset can never arm on DCE < 12

`dce110_enable_per_frame_crtc_position_reset()` loops from `i = 1` ("skip the master"),
but `enable_timing_multisync()` hands it a list containing **only** non-master pipes.
So on every DCE part below 12 the per-frame reset path has been dead code: it programs a
global swap lock, waits for a trigger that was never armed, and tears the lock down again.

Two further defects in the same area:

- `dce110_timing_generator_enable_crtc_reset()` writes a raw timing-generator **index**
  into `CRTC_TRIGB_SOURCE_SELECT`, which is an enum field
  (`TRIGGER_SOURCE_SELECT_LOGIC_ZERO = 0`, `CRTC_VSYNCA = 1`, `GSL_GROUP0 = 16`). A master
  on OTG0 therefore selects `LOGIC_ZERO`: the trigger can never fire, and
  `wait_for_reset_trigger_to_occur()` busy-waits ten frames (~167 ms) **under `dc_lock`**
  logging *"GSL: Timeout on reset trigger!"*. It also leaves `MASTER_UPDATE_MODE = 2`
  behind and never calls `disable_reset_trigger`.
- The `NEXT_LINE` branch modifies `CRTC_VERT_SYNC_CONTROL` and never writes it back.

Observed on hardware: with the flag set on both tiles, `CRTC_TRIGB_CNTL` reads `0` —
nothing armed.

Fix (gate it off for DCE < 12, plus a measured re-align):
`patches/fixes/13-dce-genlock.patch`.

---

## 3. `amdgpu_dm_force_timing_sync` is a footgun on DCE

The debugfs knob propagates `triggered_crtc_reset.enabled` to **every** stream. Attach a
60 Hz external monitor next to a 59.98 Hz panel and that monitor wins `set_master_stream()`
(integer refresh comparison), so an unrelated output gets a dead trigger armed and is left
with `FORCE_COUNT_NOW_MODE = 2`, `TRIG_SEL = 1` and `MASTER_UPDATE_MODE = 2` until its
timing generator is re-enabled — because the per-frame path never calls
`disable_reset_trigger`.

Fix: gate the knob on DCE >= 12, same patch.

---

## 4. `program_timing_sync()` drops unblanked pipes on non-DCN

`use_pipe_ctx_sync_logic` is only set in DCN resource constructors. On DCE,
`program_timing_sync()` keeps the first unblanked pipe as master and **prunes every other
unblanked pipe** from the group. Consequence: any post-commit re-synchronisation on DCE —
including the debugfs knob — is silently a no-op for displays that are actually lit. The
only alignment a DCE multi-display setup ever gets is the one-shot inside a modeset commit,
while both pipes are still blanked.

Not fixed here; worked around by measuring the scan-out phase and calling
`enable_timing_synchronization()` on the pair directly when it drifts.

---

## 5. DCE 12 `setup_panel_mode()` writes MMIO offset 0

`LE_DCE120_REG_LIST` does not include `DP_DPHY_INTERNAL_CTRL`, and `DM_CHECK_ADDR_0` is
compiled out, so on DCE 12 the source side of the alternate scrambler reset is written to
register offset 0 and never actually enabled — while the sink is told to enable it
(`DPCD 0x10A` bit 0). The signature is a link that trains to full lock but never locks
video (`0x10A = 01`, `SINK_STATUS 0x205 = 00`).

This explains the iMac Pro (DCE 12) failure that the community works around by forcing
plain DP panel mode on the second tile. Not fixed here — this project's hardware is DCE 10
and unaffected — but it is worth a patch from someone with DCE 12 hardware.

---

## 6. DCE 10 never reports displays as timing-synchronized to PowerPlay

`bw_calcs()` derives `all_displays_in_sync` for DCE 11+, but
`dce100_validate_bandwidth()` hard-codes its bandwidth output and never sets it, and the
DCE 10 clock manager never copies it into `pp_display_cfg` either. smu7 then refuses
memory-clock switching whenever more than one display is active
(`disable_mclk_switching_for_display`), so **any** DCE 10 board with two displays runs its
memory at full speed forever.

Measured on this machine with both tiles lit: memory pinned at 1362 MHz, ~48 W at 0 % GPU
load, 83 C. With the flag derived correctly: memory idles at 143 MHz, ~17 W.

Fix: `patches/fixes/19-dce10-pplib-in-sync.patch`. It is not Apple-specific — it
restores on DCE 10 what DCE 11+ already do. Reported upstream: [drm/amd#5858](https://gitlab.freedesktop.org/drm/amd/-/issues/5858).
