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

## Layout

| Path | Contents |
|---|---|
| `src/twigpad/` | The application package |
| `src/twigpad/hjt.py` | `.hjt` reader and writer (no Qt) |
| `src/twigpad/search.py`, `links.py`, `export.py`, `model.py`, `rtf.py` | Core logic (no Qt) |
| `src/twigpad/ui/` | Qt widgets: main window, tree, find dialog, link highlighter, icons |
| `src/twigpad/resources/` | Files shipped inside the package (app icon, translations in `i18n/`) |
| `tools/` | Developer scripts (`i18n_strings.py` checks the translations) |
| `data/` | Desktop integration: `.desktop` entry, AppStream metadata, MIME type |
| `docs/` | User guide and file format notes |
| `tests/` | Unit tests and sample files |

Keep file-format and search logic free of Qt imports so it stays easy to test.

## Pull requests

- One topic per pull request, with a test for the change where possible.
- Run the tests before opening it.
- Add a line under `[Unreleased]` in `CHANGELOG.md`.
- By contributing you agree your work is released under the GPL-3.0-or-later
  license of the project.
