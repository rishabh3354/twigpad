# Contributing to Twigpad

Thanks for helping. Bug reports, `.hjt` files that do not open correctly, and
pull requests are all welcome on
[GitHub](https://github.com/rishabh3354/twigpad/issues).

## Reporting a file that does not open

If a tree file opens with warnings or looks wrong, run:

```bash
twigpad --dump path/to/file.hjt
```

and include the output in the issue. Only attach the file itself if it holds
nothing private; a small file that shows the same problem is best.

## Development setup

```bash
git clone https://github.com/rishabh3354/twigpad.git
cd twigpad
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
twigpad                      # run the app
```

Without installing, you can also run it straight from the source tree:

```bash
PYTHONPATH=src python3 -m twigpad
```

## Tests

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -t .
```

`QT_QPA_PLATFORM=offscreen` lets the window tests run without a display.
`pytest` works too once the dev extras are installed.

## Translations

Every text the app shows goes through `tr("English text")` (from
`twigpad.i18n`); texts with values use named fields,
`tr("Delete {name}?").format(name=...)`, and texts that depend on a number
use `ntr("{n} node", "{n} nodes", n)`. Texts kept in tables (menu names,
say) are marked with `N_("...")` and passed through `tr()` where they are
shown. Never build a sentence from pieces or use an f-string inside `tr()`.

The translations are JSON files in `src/twigpad/resources/i18n/`, one per
language, mapping each English text to its translation (a list of plural
forms for `ntr()` texts: one for Chinese and Japanese, three for Russian, two
otherwise). To see what a language is missing:

```bash
python3 tools/i18n_strings.py --check
```

The tests fail when a language misses a text or a translation uses a field
the English text does not have. To add a language, add it to
`i18n.LANGUAGES` (and to `PLURAL_FORMS`/`plural_index` if its plurals differ),
start its file from `python3 tools/i18n_strings.py --json`, and translate.

## Store screenshots

The screenshots in `docs/screenshots/store/` (listed in the metainfo file) are
made from a sample notebook by a script, so they can be redone after the window
changes:

```bash
python3 tools/store_screenshots.py
```

It draws the real window at twice the normal size on Qt's VNC platform (a
large virtual screen; its server listens on a local port only while the script
runs) and adds a title bar, rounded corners and a shadow.

## Packaging and releases

The Snap and the AppImage are built from these files:

| Path | Contents |
|---|---|
| `snap/snapcraft.yaml` | Snap recipe: core22, the GNOME extension, PyQt5 and PyCryptodome from PyPI, Hunspell with US English |
| `packaging/appimage/build-appimage.sh` | AppImage build: a standalone Python, the pinned wheels, Hunspell and the xcb libraries, packed by appimagetool |
| `packaging/appimage/requirements.txt` | The Python packages in the AppImage, pinned with their SHA-256 sums |
| `packaging/appimage/AppRun` | Starts Twigpad inside the AppImage |
| `tools/release.py` | Builds both and uploads them |

Both use the desktop entry, AppStream metadata and MIME types in `data/` and
the icon `src/twigpad/resources/twigpad.svg`. The AppImage build pins every
download (Python, appimagetool, its runtime and the wheels) by version and
checksum, so the same commit gives the same AppImage; it runs on Debian or
Ubuntu, since the Hunspell and xcb libraries come from that system's packages.
Release AppImages are built on Ubuntu 22.04, the oldest system they support.

What the release machine needs (the script stops and says what is missing):

```bash
sudo snap install snapcraft --classic
sudo snap install lxd && sudo lxd init --auto && sudo usermod -aG lxd $USER   # snapcraft builds in LXD
sudo apt install curl file gh
snapcraft login            # once; the Snap Store login stays on this machine
gh auth login              # once
snapcraft register twigpad # once, to own the snap name
```

To make a release:

1. Set the new version in `src/twigpad/__init__.py` (`pyproject.toml` reads it
   from there) and move the `[Unreleased]` notes in `CHANGELOG.md` under
   `## [<version>]`; that section becomes the GitHub release notes.
2. Commit, then tag and push the tag: `git tag -a v<version> -m "Twigpad <version>" && git push origin v<version>`.
3. Check that everything is in place, then build and upload:

```bash
python3 tools/release.py --dry-run                  # checks tools, logins and the tag; builds nothing
python3 tools/release.py --channel stable           # build both, then upload after asking
```

| Option | Effect |
|---|---|
| `--snap-only` / `--appimage-only` | Build and upload only one package |
| `--no-upload` | Build into `dist/` only |
| `--upload-only` | Upload what is already in `dist/` |
| `--channel stable\|candidate\|beta\|edge` | Snap Store channel (default `edge`); anything but `stable` also marks the GitHub release as a pre-release |
| `--dry-run` | Print the checks and the commands without building or uploading |
| `--yes` | Upload without asking first |

The snap goes to the Snap Store with `snapcraft upload --release=<channel>`; the
AppImage and its `.zsync` update file go to the GitHub release `v<version>`
(created with `gh release create` if it does not exist yet, added to with
`gh release upload` if it does). The AppImage goes up twice, as
`Twigpad-<version>-x86_64.AppImage` and as `Twigpad-x86_64.AppImage`, so
<https://github.com/rishabh3354/twigpad/releases/latest/download/Twigpad-x86_64.AppImage>
always downloads the newest full release (GitHub's "latest" skips pre-releases,
so release AppImages with `--channel stable`). No credentials are kept in the
repository: the script uses the `snapcraft login` and `gh auth` logins of the
machine it runs on.

To build one package by hand: `snapcraft pack` in the repository root, or
`packaging/appimage/build-appimage.sh` (output in `dist/`).

## Layout

| Path | Contents |
|---|---|
| `src/twigpad/` | The application package |
| `src/twigpad/hjt.py` | `.hjt` reader and writer (no Qt) |
| `src/twigpad/search.py`, `links.py`, `export.py`, `model.py`, `rtf.py` | Core logic (no Qt) |
| `src/twigpad/ui/` | Qt widgets: main window, tree, find dialog, link highlighter, icons |
| `src/twigpad/resources/` | Files shipped inside the package (app icon, translations in `i18n/`) |
| `tools/` | Developer scripts (`i18n_strings.py` checks the translations, `store_screenshots.py` makes the store screenshots, `release.py` builds and publishes the packages) |
| `data/` | Desktop integration: `.desktop` entry, AppStream metadata, MIME type |
| `snap/`, `packaging/appimage/` | Snap and AppImage recipes |
| `docs/` | User guide and file format notes |
| `tests/` | Unit tests and sample files |

Keep file-format and search logic free of Qt imports so it stays easy to test.

## Pull requests

- One topic per pull request, with a test for the change where possible.
- Run the tests before opening it.
- Add a line under `[Unreleased]` in `CHANGELOG.md`.
- By contributing you agree your work is released under the GPL-3.0-or-later
  license of the project.
