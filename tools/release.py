#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the Twigpad snap and AppImage, then publish them.

    python3 tools/release.py --dry-run           # what would happen; checks tools and logins
    python3 tools/release.py --no-upload         # build both into dist/
    python3 tools/release.py --channel beta      # build both, upload the snap to beta and
                                                 # the AppImage to the GitHub release v<version>
    python3 tools/release.py --appimage-only     # only the AppImage (--snap-only: only the snap)
    python3 tools/release.py --upload-only       # upload what is already in dist/

The version comes from ``twigpad.__version__`` (``src/twigpad/__init__.py``,
which ``pyproject.toml`` reads). Uploads use the logins of ``snapcraft login``
and ``gh auth login``; this script never asks for or stores credentials.
Before uploading it asks for confirmation (``--yes`` skips the question).
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
APPIMAGE_SCRIPT = os.path.join(ROOT, "packaging", "appimage", "build-appimage.sh")
SNAP_NAME = "twigpad"
CHANNELS = ("stable", "candidate", "beta", "edge")


class Stop(Exception):
    """A missing tool, login or file: the release cannot go on."""


def read_version() -> str:
    """twigpad.__version__, checked against what pyproject.toml says it uses."""
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
        pyproject = fh.read()
    if 'version = { attr = "twigpad.__version__" }' not in pyproject:
        found = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
        if found:
            return found.group(1)
        raise Stop("pyproject.toml has no version and does not read twigpad.__version__")
    with open(os.path.join(ROOT, "src", "twigpad", "__init__.py"), encoding="utf-8") as fh:
        found = re.search(r'^__version__\s*=\s*"([^"]+)"', fh.read(), re.M)
    if not found:
        raise Stop("no __version__ in src/twigpad/__init__.py")
    return found.group(1)


def snap_arch() -> str:
    machine = platform.machine()
    return {"x86_64": "amd64", "aarch64": "arm64", "armv7l": "armhf"}.get(machine, machine)


def release_notes(version: str) -> Optional[str]:
    """The CHANGELOG.md section of this version, if it has one."""
    try:
        with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    found = re.search(r"^## \[?v?%s\]?[^\n]*\n(.*?)(?=^## |\Z)" % re.escape(version), text, re.M | re.S)
    return found.group(1).strip() if found else None


class Release:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.version = read_version()
        self.tag = f"v{self.version}"
        self.snap_file = os.path.join(DIST, f"{SNAP_NAME}_{self.version}_{snap_arch()}.snap")
        self.appimage_file = os.path.join(DIST, f"Twigpad-{self.version}-x86_64.AppImage")
        self.do_snap = not args.appimage_only
        self.do_appimage = not args.snap_only
        self.build = not args.upload_only
        self.upload = not args.no_upload
        self.problems: List[str] = []

    # --- running commands ---------------------------------------------------
    def say(self, text: str) -> None:
        print(text, flush=True)

    def run(self, cmd: List[str], **kw) -> None:
        """Run a command that builds or uploads (only printed in a dry run)."""
        shown = " ".join(shlex.quote(c) for c in cmd)
        if self.args.dry_run:
            self.say(f"   would run: {shown}")
            return
        self.say(f"   $ {shown}")
        result = subprocess.run(cmd, cwd=ROOT, **kw)
        if result.returncode != 0:
            raise Stop(f"command failed with exit code {result.returncode}: {shown}")

    @staticmethod
    def check(cmd: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
        """Run a read-only check; never raises for a failing command."""
        try:
            return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return subprocess.CompletedProcess(cmd, 1, "", str(exc))

    def problem(self, text: str) -> None:
        self.problems.append(text)
        self.say(f"   ✗ {text}")

    def ok(self, text: str) -> None:
        self.say(f"   ✓ {text}")

    def need_tool(self, tool: str, install: str) -> bool:
        if shutil.which(tool):
            self.ok(f"{tool} found")
            return True
        self.problem(f"{tool} is not installed. Install it with: {install}")
        return False

    # --- checks -------------------------------------------------------------
    def preflight(self) -> None:
        a = self.args
        self.say(f"Twigpad {self.version} (tag {self.tag})")
        parts = [p for p, on in (("snap", self.do_snap), ("AppImage", self.do_appimage)) if on]
        steps = (["build"] if self.build else []) + ([f"upload (snap channel: {a.channel})"] if self.upload else [])
        self.say(f"Packages: {' and '.join(parts)}; steps: {', '.join(steps) or 'none'}"
                 + ("  [dry run: nothing is built or uploaded]" if a.dry_run else ""))
        self.say("Checking tools and logins")

        if self.upload:
            dirty = self.check(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip()
            if dirty and not a.allow_dirty:
                self.problem("the working tree has uncommitted changes; commit them first so the "
                             "upload matches the tag (or pass --allow-dirty)")
            elif dirty:
                self.say("   ! uploading a build of uncommitted changes (--allow-dirty)")
            else:
                self.ok("working tree is clean")

        if self.do_snap:
            if self.build and self.need_tool("snapcraft", "sudo snap install snapcraft --classic"):
                if not (shutil.which("lxc") or shutil.which("multipass")):
                    self.problem("snapcraft needs LXD to build. Install it with: "
                                 "sudo snap install lxd && sudo lxd init --auto && "
                                 "sudo usermod -aG lxd $USER (then log in again)")
                else:
                    self.ok("LXD or Multipass found for snapcraft")
            if self.upload and (self.build or self.need_tool("snapcraft", "sudo snap install snapcraft --classic")):
                if shutil.which("snapcraft"):
                    who = self.check(["snapcraft", "whoami"])
                    if who.returncode != 0:
                        self.problem("not logged in to the Snap Store. Run: snapcraft login")
                    else:
                        user = re.search(r"^username:\s*(\S+)", who.stdout, re.M)
                        self.ok(f"logged in to the Snap Store as {user.group(1) if user else '?'}")
                        names = self.check(["snapcraft", "names"])
                        if names.returncode == 0 and not re.search(rf"^{SNAP_NAME}\s", names.stdout, re.M):
                            self.problem(f"the snap name '{SNAP_NAME}' is not registered to this account. "
                                         f"Run: snapcraft register {SNAP_NAME}")
            if not self.build and not os.path.isfile(self.snap_file):
                self.problem(f"{os.path.relpath(self.snap_file, ROOT)} does not exist; build it first")

        if self.do_appimage:
            if self.build:
                if platform.machine() != "x86_64":
                    self.problem("the AppImage can only be built on x86_64")
                for tool, pkg in (("curl", "curl"), ("apt-get", "apt"), ("dpkg-deb", "dpkg"),
                                  ("file", "file"), ("sha256sum", "coreutils")):
                    if not shutil.which(tool):
                        self.problem(f"{tool} is missing (the AppImage is built on Debian or Ubuntu). "
                                     f"Install it with: sudo apt install {pkg}")
            if self.upload and self.need_tool("gh", "sudo apt install gh  (see https://cli.github.com)"):
                if self.check(["gh", "auth", "status"]).returncode != 0:
                    self.problem("not logged in to GitHub. Run: gh auth login")
                else:
                    self.ok("logged in to GitHub")
                    remote_tag = self.check(["git", "ls-remote", "--tags", "origin", f"refs/tags/{self.tag}"])
                    if not remote_tag.stdout.strip():
                        self.problem(f"tag {self.tag} is not on GitHub yet. Create and push it: "
                                     f"git tag -a {self.tag} -m 'Twigpad {self.version}' && "
                                     f"git push origin {self.tag}")
                    else:
                        self.ok(f"tag {self.tag} is on GitHub")
                    if release_notes(self.version) is None:
                        self.say(f"   ! CHANGELOG.md has no '## [{self.version}]' section; "
                                 "the release notes will only link to the changelog")
            if not self.build and not os.path.isfile(self.appimage_file):
                self.problem(f"{os.path.relpath(self.appimage_file, ROOT)} does not exist; build it first")

        if self.problems and not a.dry_run:
            raise Stop(f"{len(self.problems)} problem(s) found; nothing was "
                       f"{'built or uploaded' if self.build else 'uploaded'}")

    # --- steps --------------------------------------------------------------
    def build_snap(self) -> None:
        self.say("Building the snap (snapcraft, in LXD)")
        os.makedirs(DIST, exist_ok=True)
        self.run(["snapcraft", "pack", "--output", self.snap_file])

    def build_appimage(self) -> None:
        self.say("Building the AppImage")
        os.makedirs(DIST, exist_ok=True)
        self.run(["bash", APPIMAGE_SCRIPT, DIST])

    def confirm_upload(self) -> None:
        if self.args.dry_run or self.args.yes:
            return
        targets = []
        if self.do_snap:
            targets.append(f"{os.path.basename(self.snap_file)} to the Snap Store ({self.args.channel})")
        if self.do_appimage:
            targets.append(f"{os.path.basename(self.appimage_file)} to the GitHub release {self.tag}")
        if not sys.stdin.isatty():
            raise Stop("not asking for confirmation without a terminal; pass --yes to upload")
        answer = input("Upload " + " and ".join(targets) + "? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            raise Stop("upload cancelled")

    def upload_snap(self) -> None:
        self.say(f"Uploading the snap to the {self.args.channel} channel")
        self.run(["snapcraft", "upload", f"--release={self.args.channel}", self.snap_file])

    def upload_appimage(self) -> None:
        files = [self.appimage_file]
        zsync = self.appimage_file + ".zsync"
        if os.path.isfile(zsync) or self.args.dry_run:   # appimagetool writes it beside the AppImage
            files.append(zsync)
        exists = shutil.which("gh") is not None and self.check(["gh", "release", "view", self.tag]).returncode == 0
        if exists:
            self.say(f"Adding the AppImage to the existing GitHub release {self.tag}")
            self.run(["gh", "release", "upload", self.tag, "--clobber", *files])
            return
        self.say(f"Creating the GitHub release {self.tag} with the AppImage")
        notes = release_notes(self.version) or (
            f"See [CHANGELOG.md](https://github.com/rishabh3354/twigpad/blob/{self.tag}/CHANGELOG.md).")
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(notes + "\n")
        try:
            cmd = ["gh", "release", "create", self.tag, "--verify-tag", "--title", f"Twigpad {self.version}",
                   "--notes-file", fh.name]
            if self.args.channel != "stable":
                cmd.append("--prerelease")
            self.run(cmd + files)
        finally:
            os.unlink(fh.name)

    def main(self) -> None:
        self.preflight()
        if self.build:
            if self.do_snap:
                self.build_snap()
            if self.do_appimage:
                self.build_appimage()
        if self.upload:
            self.confirm_upload()
            if self.do_snap:
                self.upload_snap()
            if self.do_appimage:
                self.upload_appimage()
        if not self.args.dry_run:
            self.say("Done.")
        elif self.problems:
            raise Stop(f"dry run: a real run would stop on the {len(self.problems)} problem(s) marked ✗ above")
        else:
            self.say("Dry run finished: everything needed is in place.")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build and publish the Twigpad snap and AppImage.")
    only = p.add_mutually_exclusive_group()
    only.add_argument("--snap-only", action="store_true", help="only the snap")
    only.add_argument("--appimage-only", action="store_true", help="only the AppImage")
    steps = p.add_mutually_exclusive_group()
    steps.add_argument("--no-upload", action="store_true", help="build, but do not upload")
    steps.add_argument("--upload-only", action="store_true", help="upload what is already in dist/")
    p.add_argument("--channel", choices=CHANNELS, default="edge",
                   help="Snap Store channel to release to (default: edge). Anything but stable "
                        "also marks the GitHub release as a pre-release.")
    p.add_argument("--dry-run", action="store_true",
                   help="check tools and logins and print the commands, without building or uploading")
    p.add_argument("--yes", action="store_true", help="upload without asking first")
    p.add_argument("--allow-dirty", action="store_true", help="upload even with uncommitted changes")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        Release(parse_args(argv)).main()
    except Stop as exc:
        print(f"release: stopped: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("release: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
