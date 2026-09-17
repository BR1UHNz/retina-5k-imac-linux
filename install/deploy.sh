#!/usr/bin/bash
# deploy.sh -- install (or with --remove, uninstall) the native-5K tooling. Run with sudo.
#   sudo ./deploy.sh          install tooling + the 7.2 stack, queue builds for installed kernels
#   sudo ./deploy.sh --remove remove everything; every kernel returns to stock amdgpu at its next boot
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$0")")"
[[ $EUID == 0 ]] || { echo "run with sudo" >&2; exit 1; }

if [[ ${1:-} == --remove ]]; then
    systemctl disable --now imac5k-catchup.service imac5k-mark-ok.path 2>/dev/null || true
    systemctl --global disable imac5k-session-check.service 2>/dev/null || true
    for k in /usr/lib/modules/*/; do
        k=$(basename "$k"); [[ -d /usr/lib/modules/$k/updates/imac5k ]] || continue
        rm -rf "/usr/lib/modules/$k/updates/imac5k"; depmod -a "$k"
        if [[ -f /boot/initramfs-$k.img ]] && lsinitrd "/boot/initramfs-$k.img" 2>/dev/null | grep 'updates/imac5k' >/dev/null; then dracut -f --kver "$k" "/boot/initramfs-$k.img"; fi
    done
    rm -f /etc/kernel/install.d/45-imac5k.install /etc/kernel/install.d/96-imac5k-queue.install /etc/kernel/install.d/96-imac5k.install \
          /etc/systemd/system/imac5k-build@.service /etc/systemd/system/imac5k-catchup.service /etc/systemd/system/imac5k-ensure.service \
          /etc/systemd/system/imac5k-mark-ok.path /etc/systemd/system/imac5k-mark-ok.service /etc/systemd/user/imac5k-session-check.service \
          /usr/local/sbin/imac5k-kmod /usr/local/sbin/imac5k-build-module /usr/local/sbin/imac5k-session-check /usr/local/sbin/imac5k-build /usr/local/sbin/imac5k-ensure \
          /etc/depmod.d/imac5k.conf /etc/depmod.d/imac5k-*.conf /etc/sysusers.d/imac5k.conf /etc/tmpfiles.d/imac5k.conf
    rm -rf /usr/local/share/imac5k /usr/local/libexec/imac5k /var/lib/imac5k /var/cache/imac5k
    systemctl daemon-reload
    echo "removed; kernels use stock amdgpu from their next boot (the keeper imac5k-wake stays and gives two-output 5K)"
    exit 0
fi

install -D -m 0644 etc/sysusers.d/imac5k.conf /etc/sysusers.d/imac5k.conf
install -D -m 0644 etc/tmpfiles.d/imac5k.conf /etc/tmpfiles.d/imac5k.conf
install -D -m 0644 etc/depmod.d/imac5k.conf /etc/depmod.d/imac5k.conf
systemd-sysusers /etc/sysusers.d/imac5k.conf
systemd-tmpfiles --create /etc/tmpfiles.d/imac5k.conf
install -m 0755 sbin/imac5k-kmod sbin/imac5k-build-module sbin/imac5k-session-check -t /usr/local/sbin/
install -d -m 0755 /usr/local/share/imac5k/stack /etc/kernel/install.d
install -m 0644 README.md /usr/local/share/imac5k/README.md   # operator manual
install -m 0755 kernel-install/45-imac5k.install kernel-install/96-imac5k-queue.install -t /etc/kernel/install.d/
rm -f /etc/kernel/install.d/96-imac5k.install
install -m 0644 systemd/imac5k-build@.service systemd/imac5k-catchup.service systemd/imac5k-mark-ok.path systemd/imac5k-mark-ok.service -t /etc/systemd/system/
install -D -m 0644 systemd/user/imac5k-session-check.service /etc/systemd/user/imac5k-session-check.service
rm -f /etc/depmod.d/imac5k-*.conf
restorecon -RF /usr/local/sbin /usr/local/share/imac5k /etc/kernel/install.d /etc/systemd/system /etc/systemd/user /etc/depmod.d /etc/sysusers.d /etc/tmpfiles.d /var/lib/imac5k /var/cache/imac5k 2>/dev/null || true
systemctl daemon-reload
systemctl enable imac5k-catchup.service imac5k-mark-ok.path
systemctl --global enable imac5k-session-check.service
systemctl start imac5k-mark-ok.path
SERIES=${IMAC5K_SERIES:-$(cut -d. -f1-2 <<<"$(uname -r)")}
[[ -d stack/$SERIES ]] || { echo "no stack for kernel series $SERIES; run ./mkstack.sh $SERIES first" >&2; exit 1; }
echo "tooling installed; deploying the $SERIES stack (this queues the builds)"
/usr/local/sbin/imac5k-kmod deploy-stack "$(pwd)/stack/$SERIES"
echo "watch with: journalctl -fu 'imac5k-build@*'   status: imac5k-kmod status"
