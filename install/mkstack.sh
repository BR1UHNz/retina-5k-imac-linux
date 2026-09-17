#!/usr/bin/bash
# mkstack.sh [SERIES] -- assemble the deployable patch stack for one kernel series from
# ../patches/community (in its series order) followed by ../patches/fixes (numeric order).
# Writes stack/<SERIES>/{series,SERIES,SHA256SUMS,*.patch}, which imac5k-kmod deploy-stack takes.
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$0")")"
SERIES=${1:-7.2}
[[ $SERIES =~ ^[0-9]+\.[0-9]+$ ]] || { echo "usage: $0 [kernel series, e.g. 7.2]" >&2; exit 2; }
src=../patches
out=stack/$SERIES
rm -rf "$out"; mkdir -p "$out"
: > "$out/series"
while read -r p; do
    [[ -z $p || $p == \#* ]] && continue
    [[ -f $src/community/$p ]] || { echo "missing $src/community/$p" >&2; exit 1; }
    cp "$src/community/$p" "$out/$p"; printf '%s\n' "$p" >> "$out/series"
done < "$src/community/series"
for f in $(ls "$src"/fixes/*.patch | sort -V); do
    cp "$f" "$out/"; basename "$f" >> "$out/series"
done
printf '%s\n' "$SERIES" > "$out/SERIES"
(cd "$out" && sha256sum -- *.patch > SHA256SUMS)
echo "$out: $(grep -c . "$out/series") patches"
