# Native 5K on the iMac15,1 -- operator manual

The panel is a 2x1 tiled 5120x2880 display. Apple's firmware leaves it in a single-link 4K
mode when GRUB boots; the patched amdgpu ("5K module") wakes the second tile (vendor DPCD
0x4F1 on eDP-1), drives both 2560x2880 tiles genlocked from one CRTC and presents ONE
5120x2880 output to KDE. Fedora's stock amdgpu cannot; on a stock boot the userspace keeper
(`imac5k-wake.service`) still gives 5K as two KDE outputs.

## What runs when

| Event | What happens |
|---|---|
| `dnf`/Discover installs a kernel | `kernel-install` runs `45-imac5k.install` (restores a cached module if one exists for that exact kernel; sub-second) and `96-imac5k-queue.install` (starts `imac5k-build@KVER.service`). |
| `imac5k-build@KVER.service` | Downloads the exact Fedora source rpm from Koji (signature-checked against the Fedora key), applies the patch stack for that kernel series, compiles `amdgpu` as the unprivileged `imac5k` user, validates the result (`module_ok`: kernel signature, name, `tiled_stitch` parameter, dependency set identical to stock, CRC32 xz), installs it as `/usr/lib/modules/KVER/updates/imac5k/amdgpu.ko.xz` (depmod override) and regenerates that kernel's initramfs, verifying that it packed the 5K module (Fedora's host-only initramfs carries amdgpu for Plymouth, so the packed module is the one that boots). About 6 minutes; a restart is held back meanwhile and desktop notices say when it is safe. |
| every boot: `imac5k-catchup.service` | Queues builds for kernels that lack the module (newest kernel first; older ones after the newest is confirmed), removes state of uninstalled kernels, and stamps the boot. A stamp left over from an earlier boot means that boot ran the 5K module, never confirmed the panel, and never shut down cleanly -- it hung or was power-cycled -- so it is counted against that kernel. |
| boot + 90 s: `imac5k-confirm.timer` | Asks sysfs directly whether the stitched panel came up: `eDP-1` offers the merged `5120x2880` mode only when both tiles are stitched (split mode tops out at `2560x2880` per connector). If it is up, records `boot-ok`; if not, counts the boot. Needs no user session, compositor or login. |
| clean shutdown: `imac5k-bootstamp.service` | Clears the boot stamp, so a deliberate restart is never mistaken for a driver failure. |
| every login: `imac5k-session-check` (user unit) | Replays notices that arrived while nobody was logged in, and records `boot-ok` once KWin has eDP-1 at 5120x2880 (through `imac5k-mark-ok.path`). A redundant fast path; the 90-second timer is the one that decides. |

**When the driver is taken away.** Two counted boots in a row put that kernel back on stock amdgpu.
A boot is counted only if it either reached the 90-second check without the panel up, or hung /
was power-cycled before getting there. A restart that shuts down cleanly is never counted, however
quick it was. And once a stack has brought the panel up on a kernel even once, it is treated as
known good and is never auto-reverted -- auto-revert is there to rescue a bad build on its first
boots, not to take a working driver away later.

Nothing here changes the GRUB default or the kernel command line, ever. Escape at the GRUB prompt: `rd.driver.blacklist=amdgpu modprobe.blacklist=amdgpu` (both are needed because the initramfs carries the driver).

## Commands

    imac5k-kmod status              # every kernel: stack id, module, status, boot-ok
    sudo imac5k-kmod queue KVER     # (re)build/install for one kernel
    sudo imac5k-kmod revert KVER    # back to stock amdgpu for that kernel (next boot)
    sudo imac5k-kmod deploy-stack <repo>/install/stack/<series>  # install an updated patch stack
    journalctl -u 'imac5k-build@*'  # build logs
    sudo <repo>/tools/validate5k.py      # hardware pass criteria (OTG totals, phase, DPCD, journal)

## If a patched kernel black-screens

1. Power-cycle twice. Each hung boot is counted (the boot stamp survives an unclean shutdown), and
   after two the kernel is reverted automatically (next boot stock + keeper), with a notice.
2. Or pick the previous kernel in GRUB (stock + keeper, two-output 5K).
3. Or add `modprobe.blacklist=amdgpu rd.driver.blacklist=amdgpu` to the GRUB entry (firmware
   framebuffer, no acceleration), then `sudo imac5k-kmod revert $(uname -r)`.
4. `sudo <repo>/install/deploy.sh --remove` removes everything.

## Offline updates

Discover applies updates offline (`UseOfflineUpdates=true`): a kernel installed that way boots
once on the stock driver (keeper: two outputs), the build runs during that boot, and the next
restart is native 5K. Setting `UseOfflineUpdates=false` in `~/.config/discoverrc` makes the
build happen before the restart instead. The Fedora 45 upgrade behaves like an offline update.

## New kernel series (e.g. 7.3)

`stack/<series>/` holds one series per kernel major.minor. A kernel of a series without a
stack boots stock (keeper) and a notice asks for a port. Port: rebase `patches/community/` +
`patches/fixes/` onto the new series, `./mkstack.sh <series>`, then `sudo imac5k-kmod deploy-stack`.

## Layout

    /usr/local/sbin/imac5k-kmod, imac5k-build-module, imac5k-session-check
    /usr/local/share/imac5k/stack/<series>/{series,*.patch,STACK_ID}
    /var/lib/imac5k/kernels/KVER/{status,stack,manifest,amdgpu.ko.xz,bootok,attempts,booting}
    /var/cache/imac5k/{srpms,work}   (owned by imac5k)
    /etc/kernel/install.d/{45-imac5k,96-imac5k-queue}.install
    /etc/systemd/system/{imac5k-build@,imac5k-catchup,imac5k-mark-ok,imac5k-confirm,imac5k-bootstamp}.service
    /etc/systemd/system/{imac5k-mark-ok.path,imac5k-confirm.timer}
    /etc/systemd/user/imac5k-session-check.service
    /etc/{depmod.d,sysusers.d,tmpfiles.d}/imac5k.conf
