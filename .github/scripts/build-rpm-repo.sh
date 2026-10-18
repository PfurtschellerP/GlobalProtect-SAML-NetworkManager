#!/usr/bin/env bash
# Build a (signed) RPM repository from a directory of .rpm files.
#
#   build-rpm-repo.sh <incoming-dir> <output-dir> [gpg-key-id]
#
# The repository is always rebuilt from scratch - GitHub Releases are the source
# of truth, this tree is a derived artifact. Source RPMs are release assets but
# are not added to the binary repository. Without a key id the repository is
# left unsigned, which is only useful for local testing.
#
# Layout produced:
#   *.rpm, repodata/{repomd.xml,repomd.xml.asc}, gpclient-rpm-keyring.gpg
#   .nojekyll
#
# Requires: createrepo_c and, for signed repositories, gnupg.

set -euo pipefail

INCOMING="${1:?usage: build-rpm-repo.sh <incoming-dir> <output-dir> [gpg-key-id]}"
OUTDIR="${2:?usage: build-rpm-repo.sh <incoming-dir> <output-dir> [gpg-key-id]}"
GPG_KEY="${3:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "[build-rpm-repo] $*"; }
die() { echo "[build-rpm-repo] ERROR: $*" >&2; exit 1; }

[ -d "$INCOMING" ] || die "incoming directory does not exist: $INCOMING"
command -v createrepo_c >/dev/null || die "createrepo_c is required"
if [ -n "$GPG_KEY" ]; then
    command -v gpg >/dev/null || die "gpg is required for a signed repository"
fi

mapfile -t RPMS < <(find "$INCOMING" -maxdepth 1 -type f -name '*.rpm' ! -name '*.src.rpm' -print | sort)
[ "${#RPMS[@]}" -gt 0 ] || die "no binary RPM files found in $INCOMING"

# --- Copy packages and generate metadata -----------------------------------

rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"
cp "${RPMS[@]}" "$OUTDIR/"
log "copied ${#RPMS[@]} binary package(s) to $OUTDIR"

createrepo_c "$OUTDIR" >/dev/null
[ -f "$OUTDIR/repodata/repomd.xml" ] || die "createrepo_c did not create repomd.xml"
log "generated repository metadata"

# --- Sign metadata and publish the key --------------------------------------

if [ -n "$GPG_KEY" ]; then
    gpg --batch --yes --local-user "$GPG_KEY" --detach-sign --armor \
        "$OUTDIR/repodata/repomd.xml"
    gpg --export "$GPG_KEY" > "$OUTDIR/gpclient-rpm-keyring.gpg"
    log "signed repository metadata with $GPG_KEY"
else
    log "WARNING: unsigned repository - configure it with repo_gpgcheck=0"
fi

touch "$OUTDIR/.nojekyll"

# One table row per Fedora release: use the core package filenames, which are
# validated by the RPM build and include the Fedora release and architecture.
version_rows=""
declare -A fedora_versions=()
for rpm in "${RPMS[@]}"; do
    filename="$(basename "$rpm")"
    if [[ "$filename" =~ ^network-manager-gpclient-([0-9][A-Za-z0-9.+~-]*)-[0-9]+\.fc([0-9]+)\.(x86_64|aarch64)\.rpm$ ]]; then
        version="${BASH_REMATCH[1]}"
        fedora="${BASH_REMATCH[2]}"
        fedora_versions["$fedora"]+=$'\n'"$version"
    fi
done

for fedora in $(printf '%s\n' "${!fedora_versions[@]}" | sort -n); do
    version="$(printf '%s\n' "${fedora_versions["$fedora"]}" | sed '/^$/d' | sort -V | tail -1)"
    [ -n "$version" ] || version="&mdash;"
    version_rows="$version_rows<tr><td><code>Fedora $fedora</code></td><td><code>$version</code></td></tr>"
done

INDEX="$OUTDIR/../index.html"
if [ -f "$INDEX" ]; then
    sed "s|__VERSION_ROWS_FEDORA__|$version_rows|g" "$INDEX" > "$INDEX.tmp"
    mv "$INDEX.tmp" "$INDEX"
else
    log "WARNING: $INDEX not found, Fedora versions not added to the landing page"
fi

log "repository built in $OUTDIR"
