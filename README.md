<p align="center">
  <img src="src/twigpad/resources/twigpad.svg" width="96" alt="">
</p>

<h1 align="center">Twigpad</h1>

<p align="center">
  A fast, simple hierarchical notes editor for Linux.<br>
  Your notes in a tree, your text beside it, everything in one plain-text file.
</p>

---

Twigpad is a two-pane notebook and outliner: a tree of notes on the left, the
text of the selected note on the right. Nest notes as deep as you like, move
whole branches around, and search everything at once.

## Features

- **Unlimited nesting.** Add, rename, move, sort and drag notes anywhere in the tree.
- **Search everything.** Find and replace across all note titles and text, with a list of every match.
- **Branch clipboard.** Cut, copy and paste whole branches, also between windows.
- **`.hjt` files.** Opens and saves `.hjt` tree notes files, including old-format
  files, backup copies (`.bak`, `.hjt~`), zipped backups and damaged files.
- **Merge.** Combine several files or backups into one.
- **Safe by default.** Backup copy on save, optional auto-save, atomic writes.
- **Export and print.** Export to plain text, print preview.
- **Lightweight.** Starts instantly, keyboard-driven, no account, no cloud.

## Install

Twigpad needs Python 3.8+ and PyQt5.

```bash
git clone https://github.com/rishabh3354/twigpad.git
cd twigpad
pip install --user .
twigpad
```

AppImage and Snap packages are planned.

To run from the source tree without installing:

```bash
PYTHONPATH=src python3 -m twigpad
```

## Usage

```bash
twigpad                         # open the window
twigpad notes.hjt               # open a file, a .bak backup or a .zip
twigpad --dump notes.hjt        # print a file's tree and exit
```

See the [user guide](docs/user-guide.md) for all keys and menus.

## Project layout

```
twigpad/
├── src/twigpad/        application package
│   ├── ui/             Qt windows and widgets
│   └── resources/      app icon
├── data/               desktop entry, AppStream metadata, MIME type
├── docs/               user guide and file-format notes
├── tests/              unit tests and sample files
└── pyproject.toml      package metadata
```

## Contributing

Bug reports and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the development setup and how to run the tests, and
[docs/file-format.md](docs/file-format.md) for how `.hjt` files are read and written.

## License

Twigpad is free software, released under the
[GNU General Public License v3.0 or later](LICENSE).
