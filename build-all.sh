#!/bin/bash
# Build script for creating packages for all supported distributions
# Usage: ./build-all.sh [TARGET]
#   TARGET: Optional target (ubuntu<version> or fedora44). If not specified,
#           builds for all supported distributions.
# Examples:
#   ./build-all.sh          # Build for all supported distributions
#   ./build-all.sh ubuntu22.04 # Build only for Ubuntu 22.04
#   ./build-all.sh ubuntu24.04 # Build only for Ubuntu 24.04
#   ./build-all.sh ubuntu24.10 # Build only for Ubuntu 24.10
#   ./build-all.sh ubuntu26.04 # Build only for Ubuntu 26.04
#   ./build-all.sh fedora44 # Build only for Fedora 44

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS=("ubuntu22.04" "ubuntu24.04" "ubuntu24.10" "ubuntu26.04" "fedora44")

# Check if a specific target was requested.
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "Usage: $0 [TARGET]"
    echo ""
    echo "Build packages for all supported distributions."
    echo ""
    echo "Arguments:"
    echo "  TARGET     Optional target: ubuntu22.04, ubuntu24.04, ubuntu24.10, ubuntu26.04 or fedora44"
    echo "             If not specified, builds for all supported distributions"
    echo ""
    echo "Examples:"
    echo "  $0          # Build for all supported distributions"
    echo "  $0 ubuntu22.04 # Build only for Ubuntu 22.04"
    echo "  $0 fedora44 # Build only for Fedora 44"
    exit 0
elif [ -n "${1:-}" ]; then
    TARGET="$1"
    case "$TARGET" in
        ubuntu22.04|ubuntu24.04|ubuntu24.10|ubuntu26.04)
            ;;
        fedora44)
            ;;
        *)
            echo "ERROR: Invalid target '$1'. Supported targets: ubuntu22.04, ubuntu24.04, ubuntu24.10, ubuntu26.04, fedora44" >&2
            echo "Run '$0 --help' for usage information" >&2
            exit 1
            ;;
    esac
    TARGETS=("$TARGET")
    echo "=== Building package for ${TARGETS[0]} only ==="
else
    echo "=== Building packages for ${TARGETS[*]} ==="
fi

# Enable Docker BuildKit for better caching.
export DOCKER_BUILDKIT=1

build_ubuntu() {
    local version="$1"
    local image_name="gpclient-builder:ubuntu${version}"
    local dockerfile="Dockerfile.ubuntu${version}"
    local output_dir="$SCRIPT_DIR/output/ubuntu${version}"

    echo ""
    echo "======================================"
    echo "=== Building for Ubuntu $version ==="
    echo "======================================"

    if [ ! -f "$SCRIPT_DIR/$dockerfile" ]; then
        echo "ERROR: $dockerfile not found" >&2
        echo "Run '$0 --help' for usage information"
        exit 1
    fi

    echo "=== Building Docker image from $dockerfile ==="
    docker build -f "$SCRIPT_DIR/$dockerfile" -t "$image_name" "$SCRIPT_DIR"

    echo "=== Building .deb package for Ubuntu $version ==="
    mkdir -p "$output_dir"
    chmod 777 "$output_dir"

    # Run with cache mounts for Cargo registry and Rust target directory
    # Copy version-specific control file before building
    docker run --rm \
        --name "gpclient-build-ubuntu${version}-$$" \
        -v "$output_dir:/output" \
        -v "gpclient-cargo-cache-${version}:/cargo-cache" \
        -v "gpclient-target-cache-${version}:/build/external/GlobalProtect-openconnect/target" \
        "$image_name" \
        bash -c "cp debian/control.ubuntu${version} debian/control && fakeroot dpkg-buildpackage -us -uc -b && cp -v ../*.deb /output/ && (cp -v ../*.ddeb /output/ 2>/dev/null || true)"

    echo "=== Build complete for Ubuntu $version ==="
    echo "Packages available in: $output_dir/"
    ls -lh "$output_dir/"*.deb 2>/dev/null || echo "No .deb files found"
}

build_fedora() {
    local image_name="gpclient-builder:fedora44"
    local dockerfile="Dockerfile.fedora44"
    local output_dir="$SCRIPT_DIR/output/fedora44"

    echo ""
    echo "======================================"
    echo "=== Building for Fedora 44 ==="
    echo "======================================"

    if [ ! -f "$SCRIPT_DIR/$dockerfile" ]; then
        echo "ERROR: $dockerfile not found" >&2
        exit 1
    fi

    echo "=== Building Docker image from $dockerfile ==="
    docker build -f "$SCRIPT_DIR/$dockerfile" -t "$image_name" "$SCRIPT_DIR"

    echo "=== Building RPM packages for Fedora 44 ==="
    mkdir -p "$output_dir"
    chmod 777 "$output_dir"
    docker run --rm \
        --name "gpclient-build-fedora44-$$" \
        -v "$SCRIPT_DIR:/source" \
        -v "$output_dir:/output" \
        "$image_name" \
        bash -c '
            set -euo pipefail
            root=/source
            version="$(sed -n "s/^[^ ]* ([^)]*).*$/\1/p" "$root/debian/changelog" | head -1 | sed "s/-[0-9]*$//")"
            rm -rf /output "$root/rpmbuild"
            mkdir -p /output "$root/rpmbuild"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
            git config --global --add safe.directory "$root"
            git -C "$root" submodule update --init --recursive
            tar --exclude=.git --exclude=rpmbuild --exclude=output \
                --transform "s,^source,network-manager-gpclient-$version," \
                -czf "$root/rpmbuild/SOURCES/network-manager-gpclient-$version.tar.gz" \
                -C / source
            cp "$root/rpm/network-manager-gpclient.spec" "$root/rpmbuild/SPECS/"
            rpmbuild -bb --define "project_version $version" \
                --define "_topdir $root/rpmbuild" \
                "$root/rpmbuild/SPECS/network-manager-gpclient.spec"
            find "$root/rpmbuild/RPMS" -type f -name "*.rpm" \
                ! -name "*-debugsource-*.rpm" ! -name "*-debuginfo-*.rpm" \
                -exec cp {} /output/ \;
            find "$root/rpmbuild/SRPMS" -name "*.src.rpm" -exec cp {} /output/ \;
            test -n "$(find /output -type f -name "*.rpm" -print -quit)"
        '

    echo "=== Build complete for Fedora 44 ==="
    echo "Packages available in: $output_dir/"
    ls -lh "$output_dir/"*.rpm 2>/dev/null || echo "No .rpm files found"
}

for target in "${TARGETS[@]}"; do
    case "$target" in
        ubuntu*)
            build_ubuntu "${target#ubuntu}"
            ;;
        fedora44)
            build_fedora
            ;;
    esac
done

echo ""
echo "======================================"
echo "=== All builds complete ==="
echo "======================================"
echo ""
echo "Packages summary:"
for target in "${TARGETS[@]}"; do
    output_dir="$SCRIPT_DIR/output/$target"
    echo ""
    case "$target" in
        ubuntu*) echo "Ubuntu ${target#ubuntu}:"; ls -lh "$output_dir/"*.deb 2>/dev/null || echo "  No .deb files found" ;;
        fedora44) echo "Fedora 44:"; ls -lh "$output_dir/"*.rpm 2>/dev/null || echo "  No .rpm files found" ;;
    esac
done
