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
| every boot: `imac5k-catchup.service` | Counts boots of a patched kernel that never reached a 5K desktop, auto-reverts after 2 in a row, queues builds for kernels that lack the module (newest kernel first; older ones after the newest is confirmed), removes state of uninstalled kernels. |
| every login: `imac5k-session-check` (user unit) | Replays notices that arrived while nobody was logged in; waits for eDP-1 to be at 5120x2880 and then records `boot-ok` for the running kernel (through `imac5k-mark-ok.path`). |

Nothing here changes the GRUB default or the kernel command line, ever. Escape at the GRUB prompt: `rd.driver.blacklist=amdgpu modprobe.blacklist=amdgpu` (both are needed because the initramfs carries the driver).

## Commands

    imac5k-kmod status              # every kernel: stack id, module, status, boot-ok
    sudo imac5k-kmod queue KVER     # (re)build/install for one kernel
    sudo imac5k-kmod revert KVER    # back to stock amdgpu for that kernel (next boot)
    sudo imac5k-kmod deploy-stack <repo>/install/stack/<series>  # install an updated patch stack
    journalctl -u 'imac5k-build@*'  # build logs
    sudo <repo>/tools/validate5k.py      # hardware pass criteria (OTG totals, phase, DPCD, journal)

## If a patched kernel black-screens

1. Power-cycle. After 2 boots without a confirmed desktop the kernel is reverted automatically
   (next boot stock + keeper), with a notice.
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
    /var/lib/imac5k/kernels/KVER/{status,stack,manifest,amdgpu.ko.xz,bootok,attempts}
    /var/cache/imac5k/{srpms,work}   (owned by imac5k)
    /etc/kernel/install.d/{45-imac5k,96-imac5k-queue}.install
    /etc/systemd/system/{imac5k-build@,imac5k-catchup,imac5k-mark-ok}.service, imac5k-mark-ok.path
    /etc/systemd/user/imac5k-session-check.service
    /etc/{depmod.d,sysusers.d,tmpfiles.d}/imac5k.conf
