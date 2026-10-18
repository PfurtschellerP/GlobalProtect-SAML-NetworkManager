"""The release notes' table of download links, as markdown.

    gh release view v1.4.2 --json assets,body > release.json
    release_notes.py --repo OWNER/REPO --tag v1.4.2 --release-json release.json > new-body.md

Used by .github/workflows/build-release.yml. The release has one .deb per package, Ubuntu release and architecture, and one
binary .rpm per package, Fedora release and architecture. The notes start with
tables grouped by package format. The links are those of the assets the release
has and has finished uploading. The tables are wrapped in markers and merged into the body of the
release (GitHub's generated notes): it replaces the block between the markers,
or, with no block yet, goes to the top. The rest of the body is kept byte for
byte, so a rerun changes nothing. Standard library only.
"""

import argparse
import json
import re
import sys
import urllib.parse

REPO_RE = re.compile(r"[\w.-]+/[\w.-]+", re.ASCII)
# Characters that are safe in a markdown link target
URL_RE = re.compile(r"[A-Za-z0-9._~%+/:-]+")
START = "<!-- downloads:start -->"
END = "<!-- downloads:end -->"
# <package>_<version>.<codename>1_<arch>.deb; GitHub turns the "~" of a release version
# (1.4.2-1~noble1) into "." in the name of an asset: accept either
NAME_RE = re.compile(
    r"(?P<package>[a-z0-9][a-z0-9+.-]*)_(?P<version>[0-9][A-Za-z0-9.+~-]*?)"
    r"[.~](?P<codename>[a-z]+)1_(?P<arch>[a-z0-9]+)\.deb"
)
# <package>-<version>-<release>.fc<release>.<arch>.rpm
RPM_NAME_RE = re.compile(
    r"(?P<package>network-manager-gpclient(?:-(?:gnome|plasma|plasma-6))?)-"
    r"(?P<version>[0-9][A-Za-z0-9.+~-]*)"
    r"-(?P<release>[0-9]+)\.fc(?P<fedora>[0-9]+)\.(?P<arch>x86_64|aarch64)\.rpm"
)
CORE = "network-manager-gpclient"
# Short names in the order of a cell; any other package follows alphabetically
ORDER = ["gpclient", "gnome", "plasma", "plasma-6"]
UBUNTU = {"jammy": "22.04", "noble": "24.04", "oracular": "24.10", "resolute": "26.04"}
FEDORA = {"44": "44"}
EMPTY = "—"


class NotesError(Exception):
    """Input that must not end up in the release notes."""


def short_name(package):
    if package == CORE:
        return "gpclient"
    if package.startswith(CORE + "-"):
        return package[len(CORE) + 1:]
    return package


def parse(name):
    """(codename, arch, short package name) of a package file name"""
    match = NAME_RE.fullmatch(name)
    if not match:
        raise NotesError("unexpected name of a .deb asset: %r" % (name,))
    return match.group("codename"), match.group("arch"), short_name(match.group("package"))


def parse_rpm(name):
    """(Fedora release, arch, short package name) of a binary RPM filename"""
    match = RPM_NAME_RE.fullmatch(name)
    if not match:
        raise NotesError("unexpected name of a .rpm asset: %r" % (name,))
    return match.group("fedora"), match.group("arch"), short_name(match.group("package"))


def check_url(repo, name, url):
    """`url` must be the download link of the asset `name`, and safe in markdown"""
    prefix = "https://github.com/%s/releases/download/" % repo
    if not isinstance(url, str) or not URL_RE.fullmatch(url):
        raise NotesError("unsafe url of the asset %r: %r" % (name, url))
    rest = url[len(prefix):] if url.startswith(prefix) else ""
    folder, _slash, last = rest.rpartition("/")
    if not folder or "/" in folder or last != name:
        raise NotesError("url of the asset %r is not its download link: %r" % (name, url))


def release_key(codename):
    """Known Ubuntu releases by version, then the unknown ones by codename"""
    return (0, UBUNTU[codename], "") if codename in UBUNTU else (1, "", codename)


def row_label(codename):
    if codename in UBUNTU:
        return "Ubuntu %s (%s)" % (UBUNTU[codename], codename)
    return codename


def rpm_row_label(fedora):
    return "Fedora %s" % FEDORA.get(fedora, fedora)


def fedora_release_key(fedora):
    """Known Fedora releases by version, then unknown releases numerically"""
    if fedora in FEDORA:
        return (0, int(FEDORA[fedora]))
    return (1, int(fedora))


def cell_key(item):
    short = item[0]
    return (ORDER.index(short), "") if short in ORDER else (len(ORDER), short)


def render(repo, tag, assets):
    """The marked block of markdown for the assets (dicts with name, url and state) of the release"""
    if not REPO_RE.fullmatch(repo):
        raise NotesError("repo must look like OWNER/REPO: %r" % (repo,))
    if not tag:
        raise NotesError("the tag is empty")
    debs = []
    rpms = []
    for asset in assets:
        name = asset.get("name") if isinstance(asset, dict) else None
        if not isinstance(name, str):
            raise NotesError("an asset without a name: %r" % (asset,))
        # only an asset that is "uploaded" has a download link that works
        if name.endswith(".deb") and asset.get("state") == "uploaded":
            debs.append((name, asset.get("url")))
        elif (name.endswith(".rpm") and not name.endswith(".src.rpm")
              and asset.get("state") == "uploaded"):
            rpms.append((name, asset.get("url")))
    if not debs and not rpms:
        raise NotesError("no .deb or binary .rpm assets: refusing to write a release without downloads")

    cells = {}
    seen = {}
    for name, url in debs:
        codename, arch, short = parse(name)
        check_url(repo, name, url)
        if (codename, arch, short) in seen:
            raise NotesError("two assets for the same package, release and architecture: %r and %r"
                             % (seen[codename, arch, short], name))
        seen[codename, arch, short] = name
        cells.setdefault((codename, arch), []).append((short, url))
    rpm_cells = {}
    rpm_seen = {}
    for name, url in rpms:
        fedora, arch, short = parse_rpm(name)
        check_url(repo, name, url)
        if (fedora, arch, short) in rpm_seen:
            raise NotesError("two RPM assets for the same package, release and architecture: %r and %r"
                             % (rpm_seen[fedora, arch, short], name))
        rpm_seen[fedora, arch, short] = name
        rpm_cells.setdefault((fedora, arch), []).append((short, url))

    arches = sorted({arch for _codename, arch in cells}, key=lambda a: (a != "amd64", a))
    codenames = sorted({codename for codename, _arch in cells}, key=release_key)
    rpm_arches = sorted({arch for _fedora, arch in rpm_cells}, key=lambda a: (a != "x86_64", a))
    fedora_releases = sorted({fedora for fedora, _arch in rpm_cells}, key=fedora_release_key)

    base = "https://github.com/%s" % repo
    blob = "%s/blob/%s" % (base, urllib.parse.quote(tag, safe="/"))
    lines = [START, "## Downloads", ""]
    if debs:
        lines.extend([
            "The recommended way to install Debian packages is the apt repository: see "
            "[docs/APT_REPO.md](%s/docs/APT_REPO.md). With single files, take "
            "`network-manager-gpclient` and one desktop package (`-gnome`, `-plasma` or, "
            "on KDE neon, `-plasma-6`) from the same row and architecture and install them together, "
            "e.g. `sudo apt install ./network-manager-gpclient_*.deb "
            "./network-manager-gpclient-gnome_*.deb`. On Ubuntu 22.04 `python3-sdbus` is "
            "not in apt: see the [README](%s/README.md) first." % (blob, blob),
            "",
            "| Ubuntu | " + " | ".join(arches) + " |",
            "|---|" + "---|" * len(arches),
        ])
        for codename in codenames:
            row = []
            for arch in arches:
                links = [
                    "[%s](%s)" % (short, url)
                    for short, url in sorted(cells.get((codename, arch), []), key=cell_key)
                ]
                row.append("<br>".join(links) or EMPTY)
            lines.append("| %s | %s |" % (row_label(codename), " | ".join(row)))
    if rpms:
        lines.extend([
            "",
            "The RPM packages are available from the signed RPM repository: see "
            "[docs/RPM_REPO.md](%s/docs/RPM_REPO.md)." % blob,
            "",
            "| Fedora | " + " | ".join(rpm_arches) + " |",
            "|---|" + "---|" * len(rpm_arches),
        ])
        for fedora in fedora_releases:
            row = []
            for arch in rpm_arches:
                links = [
                    "[%s](%s)" % (short, url)
                    for short, url in sorted(rpm_cells.get((fedora, arch), []), key=cell_key)
                ]
                row.append("<br>".join(links) or EMPTY)
            lines.append("| %s | %s |" % (rpm_row_label(fedora), " | ".join(row)))
    lines.append(END)
    return "\n".join(lines)


def find_block(text, what):
    """(start, end) offsets of the one marked block of `text`, or None if it has none"""
    starts = [m.start() for m in re.finditer(re.escape(START), text)]
    ends = [m.start() for m in re.finditer(re.escape(END), text)]
    if not starts and not ends:
        return None
    if len(starts) > 1 or len(ends) > 1:
        raise NotesError("%s has more than one downloads marker of a kind" % what)
    if not starts or not ends:
        raise NotesError("%s has a downloads marker without its pair" % what)
    if ends[0] < starts[0]:
        raise NotesError("%s has the downloads end marker before the start marker" % what)
    return starts[0], ends[0] + len(END)


def merge(old, block):
    """The body `old` with the marked `block` in it"""
    found = find_block(old, "the release body")
    if found is None:
        return block + "\n\n" + old
    return old[:found[0]] + block + old[found[1]:]


def read_text(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", required=True, help="OWNER/REPO of the release")
    parser.add_argument("--tag", required=True, help="the release's tag, e.g. v1.4.2")
    parser.add_argument("--release-json", required=True, metavar="FILE",
                        help="output of: gh release view TAG --json assets,body")
    args = parser.parse_args(argv)
    try:
        release = json.loads(read_text(args.release_json))
        if not isinstance(release, dict) or not isinstance(release.get("assets"), list):
            raise NotesError("the release JSON has no list of assets")
        body = release.get("body")
        if body is None:
            body = ""
        if not isinstance(body, str):
            raise NotesError("the release JSON has a body that is not text")
        text = merge(body, render(args.repo, args.tag, release["assets"]))
    except (OSError, ValueError) as exc:
        print("error: cannot read the input: %s" % exc, file=sys.stderr)
        return 1
    except NotesError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
