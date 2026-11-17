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
- Classic tree look: folder icons, dotted connector lines, +/- boxes and a
  title-only selection highlight (View → Classic Tree Look, on by default).
- Format menu: UPPERCASE, lowercase, Remove Leading Spaces, and Remove Leading
  Spaces and Returns (cleans up quoted, hard-wrapped email text).
- Import several text files at once, and CSV files (one node per row).
- Edit → Insert → Text from File.
- Export as an HTML web page (with a table of contents) and export a branch as
  a separate `.hjt` file.
- Node → Next Siblings Move Right and All Children Move Left; Copy and Paste
  Node Name.
- View → Tree and Article / Tree Only / Article Only; expand or collapse the
  selected branch one level or all levels.
- File → Read Only, switched on automatically for files you can't write to.
- File → Print Whole File.
- File → Minimize to Tray (Ctrl+M).
- Options → Automatic Paste: text copied in other programs is collected in the
  current article.
- Portable settings: put an empty `twigpad.ini` next to the program or
  AppImage to keep the settings there.
- Focus on a branch (Ctrl+]): show only the selected note and the notes under
  it; Ctrl+[ goes back up a level.
- Tabs: open a branch in its own tab (Ctrl+T); each tab remembers its place.
- Backlinks panel: which notes link to the selected one.
- Tags: write #tags in titles or articles; the Tags panel lists every tag and
  the notes that use it.
- Word count in the status bar (for the selection too) and Edit → Word Count
  for the note, branch and whole file.
- Warns when the open file is changed or deleted by another program, and asks
  before saving over someone else's changes.
- Spell checking with the system's Hunspell dictionaries: misspelled words are
  underlined; right-click for suggestions or Add to Dictionary.
- New `.twig` file format for what `.hjt` can't hold. `.hjt` files stay plain
  text and are only changed when you choose to save them as plain `.hjt`.
- Formatted notes: bold, italic, underline, strikethrough, colours, fonts,
  headings, lists, alignment, tables, horizontal lines and pictures
  (inserted or pasted). Exported to HTML and printed with their formatting.
- Note icons and colours (Node → Icon and Colour).
- Password protection: File → Set Password encrypts the file (AES-256-GCM
  with PyCryptodome, key from scrypt).
- View → Theme: polished Light and Dark themes, Automatic (follows the
  desktop's light or dark setting, the default) and Desktop Style.
- Help → Report a Bug opens a new GitHub issue with the app and system
  versions filled in; the About window links to it too. Help → Request a
  Feature opens one for ideas.
- Undo and redo for the tree (Ctrl+Z / Ctrl+Y in the tree, Edit menu and
  right-click menu): adding, deleting, renaming, moving and dragging nodes,
  cut and paste, sorting, importing, Replace All and icon changes. A deleted
  branch comes back in place with its subnodes, articles and open branches.
  Edit → Undo names the step it will undo.
- Help → Keyboard Shortcuts (F1, Ctrl+/): every shortcut, grouped by menu,
  with a search box.
- Crash recovery: unsaved changes are copied every 30 seconds and offered
  back at the next start after a crash or power cut (encrypted for
  password-protected files).
- File → Backup & Restore: back up notes files and settings into one .zip and
  restore them on another computer; files already there are skipped.
- Options → Spelling Language → Download Languages: about 50 dictionaries
  to download with one click; the menu shows language names.
- View → Fonts: interface, tree and article fonts and sizes with a live
  preview. A clean default font (Inter or Noto Sans) and slightly larger
  default text.
- Options → Open .hjt Files with Twigpad (also offered once at first start)
  makes the file manager open .hjt and .twig files in Twigpad.
- Options → Reset All Settings to Defaults (notes, recent files and
  dictionary words are kept).
- Help → Support the Developer (Donate), More Apps by Warlord Softwares and
  About the Developer; a new About window with the same links.
- View → Language: menus and windows in English, German, French, Spanish,
  Italian, Brazilian Portuguese, Russian, Simplified Chinese and Japanese.
  Automatic (the default) follows the desktop's language; choosing another
  one offers to restart Twigpad. `--language CODE` picks one for a single
  start. Qt's own texts (file dialogs) follow too.
- View → Colours: background and text colours for the tree and the article.
- Options → At Startup (reopen the last file, ask, Quick Start window, or a
  new file) and When Closing With Unsaved Changes (ask, save, don't save).
- Options → Use Tab to Switch Between Tree and Article (Ctrl+Tab then types a
  tab), Minimize to Tray Instead of the Taskbar, and Keep Settings Next to
  the Program.
- Cut and Copy take the whole article when nothing is selected; Edit → Delete
  clears the whole article after asking.
- File → Import → Text File into Article (Replace Its Text).
- The classic five movable toolbars, in the classic order and with the
  classic buttons: File (with an Options button), Article Edit, Tree Edit,
  View (Find, Search Tree, view modes, Word Wrap) and Navigate (Follow Link,
  move node, expand/collapse branch), plus an optional Extras toolbar.
- Modern toolbar icons: one consistent set of rounded outline icons with
  accent colours, drawn by Twigpad so they look the same on every desktop and
  follow the light and dark themes.
- Flat, modern folder icons in the tree.
- A refreshed, more modern app logo.
- Larger toolbar icons (24 px) by default; View → Toolbars → Icon Size
  offers Small, Medium, Large and Extra Large, and Button Labels shows the
  names beside or under the icons. Toolbars wrap onto more rows when needed.
- View → Text Size for the tree and the article (Ctrl+=, Ctrl+-, Ctrl+0 and
  Ctrl+mouse wheel), and View → Tree Icon Size.
- The More Apps window shows each app's own icon.
- Tree Search window (Ctrl+F in the tree, or Search → Search Tree, Shift+F11):
  search the total tree or a subtree, in titles and/or articles, with a
  numbered results list showing where each match is (Node, Article or
  Article+Node) and the node's path; double-click or Enter selects the node,
  and Search Article steps through the matches in its article.
- Shift+drop onto a node puts the dragged node below it; a slow second click
  renames a node; Ctrl+Up/Down scroll the tree; Shift+F10 opens the
  right-click menu; Find and Go to Start/End in the article's right-click
  menu.
- Five store screenshots (`docs/screenshots/store/`), listed in the metainfo
  file, and `tools/store_screenshots.py` to make them again.
- Snap (`snap/snapcraft.yaml`) and AppImage (`packaging/appimage/`) packages,
  both with the Hunspell spell checker and a US English dictionary, and
  `tools/release.py` to build them and publish them to the Snap Store and
  GitHub releases.

### Changed
- A file has exactly one top node, as the `.hjt` format requires. Files with
  several top-level nodes are opened under a new top node.
- Replace moved to Ctrl+R (Ctrl+H now follows links); Save As is Ctrl+Alt+S.
- Ctrl+V in the tree pastes inside the selected node; Ctrl+Shift+V pastes below.
- Ctrl+F searches the selected node when pressed in the article, and the whole
  file when pressed in the tree.
- One fixed toolbar became five movable ones; Cut and Copy are always enabled.
- The desktop entry, icon and AppStream id are now `com.warlordsoftwares.twigpad`.
- Messages and questions use Twigpad's own windows: a clear heading, an icon,
  buttons named for what they do (Delete, Don't Save, Reload) and light and
  dark theme colours. Password prompts use the same style.
- View → Article Font and Tree Font became one Fonts window.

### Fixed
- Tab close buttons are a sharp × in the theme's text colour; the old one was
  blurry on large screens and almost invisible in the dark theme.
- The box for renaming a node in the tree no longer cuts off the bottom of the title.
- Zooming the tree with Ctrl+mouse wheel now also resizes the note icons.
