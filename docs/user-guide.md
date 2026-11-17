# Twigpad user guide

Twigpad keeps notes in a tree. The left pane shows the tree of **nodes**; the
right pane shows the **article** (the text) of the selected node. A whole tree
is saved as one `.hjt` file.

## Working with nodes

Node keys work while the tree pane has the keyboard focus (press **F6** to
switch panes). The same commands are in the **Node** menu and on right-click.

| Key | Action |
|---|---|
| Ins | Add a child node inside the selected one |
| Shift+Ins or Enter | Add a node below the selected one |
| Ctrl+Shift+Ins | Add a node above the selected one |
| F2 | Rename |
| Del | Delete the node and everything inside it (asks first) |
| Shift+Up / Down | Move up / down among its siblings |
| Shift+Left | Move out one level |
| Shift+Right | Move in one level (under the node above) |
| Alt+Up / Down | Go to the previous / next node at the same level |
| + / − | Expand / collapse the node |
| Ctrl+X / Ctrl+C | Cut / copy the node with its subnodes |
| Ctrl+V | Paste inside the selected node |
| Ctrl+Shift+V | Paste below the selected node |
| Ctrl+Shift+H | Copy a link to the node (see Links) |
| Ctrl+Shift+S | Sort the subnodes of the selected node by title |

**Node → Sort Whole Tree** sorts every level. You can also drag a node onto
another node (to put it inside) or between two nodes.

More in the **Node** menu:

- **Next Siblings Move Right**: the nodes below the selected one, at the same
  level, move inside it.
- **All Children Move Left**: the nodes inside the selected one move out a
  level, to just below it.
- **Copy Node Name** copies the title; **Paste Node Name** renames the node to
  the first line of the clipboard.

### The top node

A file has exactly one top node, which holds everything else. You can rename
it and add nodes inside it, but not delete it, move it, or add nodes next to
it. A file that has several top-level nodes (made by another program) is
opened with a new top node around them; Twigpad tells you when it does this.

Copied nodes can be pasted into another Twigpad window. Text copied from any
other program can be pasted in the tree too: it becomes a new node titled by
its first line.

## Editing articles

| Key | Action |
|---|---|
| F5 | Insert date and time |
| Ctrl+Shift+D / Ctrl+Shift+T | Insert date / time |
| Ctrl+Z / Ctrl+Y | Undo / redo (per node) |
| Ctrl+H | Follow the link at the cursor |
| Ctrl+Tab or F6 | Switch between tree and article |

**Edit → Insert → Text from File** inserts a text file at the cursor.

The **Format** menu changes the selected text, or the whole article when
nothing is selected (Ctrl+Z undoes it):

| Command | What it does |
|---|---|
| UPPERCASE / lowercase | Changes letter case |
| Remove Leading Spaces | Removes spaces and tabs at the start of each line |
| Remove Leading Spaces and Returns | Removes indentation and `>` quote marks, and joins wrapped lines into paragraphs: for text pasted from an email |

## View

- **Tree and Article**, **Tree Only** or **Article Only** chooses which panes
  are shown; Twigpad remembers the choice.
- **Expand / Collapse Selected Node** opens or closes one branch, one level or
  all levels deep; **Expand All** and **Collapse All** do the whole tree.
- Word wrap, and separate fonts for the tree and the article.
- **Classic Tree Look** switches between the classic tree (folder icons,
  dotted lines, +/- boxes) and your desktop's standard tree style.

## Links

Links are written in square brackets in the article and shown underlined:

| Link | Opens |
|---|---|
| `[http://example.com]`, `[www.example.com]` | the web page in your browser |
| `[mailto:name@example.com]` | your email program |
| `[file:///home/me/report.pdf]`, `[file://notes/todo.txt]` | the file or folder; a relative path is relative to the open `.hjt` file |
| `[node://My notes/Recipes/Soup]` | another node in this file (the path of titles from the top node; case does not matter) |

Put the cursor inside a link and press **Ctrl+H**, or **Ctrl+click** it. Links
without spaces also work without brackets. For a link with spaces and no
brackets, select the whole link first, or put it in double quotes.

- To link to a node: select it, press **Ctrl+Shift+H** (Node → Copy Node Link
  Address), then paste the link into any article.
- To link to a file or folder: **Edit → Insert Link**.

## Search

| Key | Action |
|---|---|
| Ctrl+F or Shift+F12 | Find |
| Ctrl+R | Find and replace |
| F3 / Shift+F3 | Find next / previous |

Search looks in node titles, articles, or both; in all nodes, the selected
branch, or the selected node only. Options: match case, whole words, regular
expressions. **Find All** lists every match; click one to jump to it.
**Replace All** reports how many replacements it made.

## Files and backups

- **Open** accepts `.hjt` files, backup copies (`.bak`, `.hjt~`) and `.zip`
  archives that contain a `.hjt` file. Backups are opened as a new unsaved
  file, so **Save** asks for a new name instead of overwriting the backup.
- Damaged or cut-off files are opened as far as possible; a message lists
  what was repaired.
- **File → Import → Tree File or Backup** adds every node of another file
  inside the selected node, for combining several files into one.
- **File → Import → Text Files** adds one or more text files, each as a new
  node. **CSV File** adds a node per row: the first column is the title, the
  other columns become the article.
- **File → Export** writes the selected node, its branch or the whole file as
  a numbered text outline or as an HTML web page with a table of contents.
  **Selected Node and Subnodes as Tree File** saves a branch as its own `.hjt`
  file.
- **File → Print** shows a print preview of the selected branch, the selected
  node only, or the whole file.
- **File → Read Only** protects the file from changes. Files you don't have
  permission to change are opened read only; **Save** then asks for a new name.
- **File → Minimize to Tray** (Ctrl+M) hides the window to the system tray;
  click the tray icon to bring it back. Without a tray it minimizes normally.
- Files are saved in the Windows-compatible encoding when possible, so they
  stay readable by other programs that use the `.hjt` format.

### Options menu

| Option | Default |
|---|---|
| Open last file at startup | On |
| Keep a backup copy (`<file>.hjt.bak`) when saving: the file as it was when you opened it | On |
| Auto-save every 5 minutes | Off |
| Automatic Paste: text you copy in other programs is added to the end of the current article (for collecting snippets) | Off, not remembered |

### Portable use

To run Twigpad from a USB stick, create an empty file called `twigpad.ini`
next to the AppImage (or the `twigpad` program). Twigpad then keeps its
settings in that file instead of your home folder.

## Command line

```bash
twigpad [FILE]                 # open the window, optionally with a file
twigpad --dump FILE [--text]   # print a file's tree (and text) and exit
twigpad --version
```
