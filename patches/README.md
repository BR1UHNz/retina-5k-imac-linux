# The patch stack

Applied in this order, with `patch -p1 --fuzz=0`, against a prepared Fedora kernel source
tree. `install/mkstack.sh` assembles exactly this order into `install/stack/<series>/`.

## `community/` — the base (GPL-2.0, redistributed unmodified)

From **[MarkPronkin/imac5k-universal-linux-patcher](https://github.com/MarkPronkin/imac5k-universal-linux-patcher)**
at `c1086d2`, which in turn carries work by **ahmadtv** (lean core for 7.2.x) and builds on
**[mcirsta/linux-imac-5k](https://github.com/mcirsta/linux-imac-5k)**.

1. `imac5k-lean-core-7.2.x.patch` — panel quirk, tile pairing, the vendor wake, link bring-up
2. `imac5k-stitch-layer-7.x.patch` — drives both tiles from one CRTC and presents one output
3. `5k-going-down-stop-resync.patch`
4. `5k-post-commit-link-recovery.patch`
5. `5k-logical-modeset-guard.patch`
6. `5k-resume-drop-cached-peer.patch`
7. `5k-resume-arm-link-health.patch`
8. `imacpro-slave-dp-panel-mode.patch` — iMac Pro only; inert here
9. `dce120-enable-crtc-reset.patch` — DCE 12 only; inert here
10. `dce12-multisync-master-first.patch` — DCE 12 only; inert here
11. `dce110-genlock-master-from-pipe0.patch`
12. `5k-resync-postpone-on-modeset.patch`

Use pronkin's copy of the lean core, not ahmadtv's: the latter predates `42408b4` and
fails `Hunk #2` in `amdgpu_dm_helpers.c` on 7.2.5.

## `fixes/` — added here

13. `13-dce-genlock.patch` — global swap-lock register addressing; gate the dead
    per-frame reset path off on DCE < 12; measured tile re-align in its place
14. `14-stitch-gate.patch` — never leave the internal panel with zero modes; retrying
    EDID re-read; right-tile re-attach on hotplug; DRM-lease guard; sticky non-desktop flag
15. `15-stitch-planes.patch` — plane-geometry guard; attach the second tile on every
    commit; refresh its buffer address in `prepare_fb`; refuse tearing flips
16. `16-link-lifecycle.patch` — fixed tile pairing (no Thunderbolt re-pairing);
    idempotent wake; wake from the root link's own power-up; 20 ms AUX-ready spacing;
    shutdown handoff from the root; recovery via link-status instead of a power cycle;
    GPU-reset arming
17. `17-ahmadtv-amdgpu-hpd-skip-during-reset.patch` — **ahmadtv's patch, unmodified** (drm/amd#5810)
18. `18-ahmadtv-amdgpu-vce-suspend-in-reset.patch` — **ahmadtv's patch, unmodified** (drm/amd#5810)
19. `19-dce10-pplib-in-sync.patch` — report timing-synchronized displays to PowerPlay
    on DCE 10, so the memory clock can idle
20. `20-fixups-1.patch` — bound the recovery escalation per boot; EDID swap under lock

Do **not** carry ahmadtv's `amdgpu-vce3-ring-align-mask.patch` on Tonga: Tonga sorts below
`CHIP_STONEY` and uses `vce_v3_0_ring_phys_funcs`, which has no `insert_end`.

## Other kernel series

`install/stack/<major>.<minor>/` holds one stack per kernel series, so kernels from
different series can be installed side by side. Only **7.2** is present and tested. 7.3
moves code into `amdgpu_dm_connector.c` and needs a port; a kernel from an unsupported
series boots the stock driver and raises a desktop notice.
