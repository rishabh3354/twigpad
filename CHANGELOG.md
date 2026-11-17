# Changelog

All notable changes to Twigpad are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Two-pane window: tree of nodes on the left, plain-text article on the right.
- Open and save `.hjt` tree files, including old-format files, Windows-encoded
  files, backup copies (`.bak`, `.hjt~`), zipped backups and damaged or
  truncated files.
- Add, rename, delete, move and drag-and-drop nodes; sort subnodes.
- Cut, copy and paste nodes with their subnodes, also between windows.
- Find and Replace across titles and articles, with Find All results list.
- Merge another tree file or backup into the current file; import text files.
- Export to text, print preview, insert date/time, fonts, word wrap.
- Recent files, reopen last file, backup copy on save, optional auto-save.
- `--dump` command-line option to print a file's tree.
- Classic tree-notepad keys: Ins adds a child, Shift+Ins or Enter adds below,
  Ctrl+Shift+Ins adds above, Shift+arrows move, Alt+Up/Down jump between
  siblings, Ctrl+Shift+S sorts, Ctrl+Tab switches panes.
- Links in articles: web, email, file and `[node://…]` links to other nodes,
  shown underlined and opened with Ctrl+H or Ctrl+click; Copy Node Link
  Address (Ctrl+Shift+H); Edit → Insert Link to a file or folder.
- Sort Whole Tree (all levels).

### Changed
- A file has exactly one top node, as the `.hjt` format requires. Files with
  several top-level nodes are opened under a new top node.
- Replace moved to Ctrl+R (Ctrl+H now follows links); Save As is Ctrl+Alt+S.
- Ctrl+V in the tree pastes inside the selected node; Ctrl+Shift+V pastes below.
