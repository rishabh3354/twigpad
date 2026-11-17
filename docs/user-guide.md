# Twigpad user guide

Twigpad keeps notes in a tree. The left pane shows the tree of **nodes**; the
right pane shows the **article** (the text) of the selected node. A whole tree
is saved as one `.hjt` file.

## Working with nodes

Node keys work while the tree pane has the keyboard focus (press **F6** to
switch panes). The same commands are in the **Node** menu and on right-click.

| Key | Action |
|---|---|
| Ins | Add a node below the selected one |
| Shift+Ins | Add a node above the selected one |
| Ctrl+Ins | Add a child node inside the selected one |
| F2 | Rename |
| Del | Delete the node and everything inside it (asks first) |
| Ctrl+Shift+Up / Down | Move up / down among its siblings |
| Ctrl+Shift+Left | Move out one level |
| Ctrl+Shift+Right | Move in one level (under the node above) |
| Ctrl+X / Ctrl+C / Ctrl+V | Cut / copy / paste the node with its subnodes |
| Ctrl+Shift+V | Paste inside the selected node |

You can also drag a node onto another node (to put it inside) or between two
nodes. **Node → Sort Subnodes A-Z** sorts the children of the selected node.

Copied nodes can be pasted into another Twigpad window. Text copied from any
other program can be pasted in the tree too: it becomes a new node titled by
its first line.

## Editing articles

| Key | Action |
|---|---|
| F5 | Insert date and time |
| Ctrl+Shift+D / Ctrl+Shift+T | Insert date / time |
| Ctrl+Z / Ctrl+Y | Undo / redo (per node) |

**View** sets word wrap and separate fonts for the tree and the article.

## Search

| Key | Action |
|---|---|
| Ctrl+F | Find |
| Ctrl+H | Find and replace |
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
- **File → Import → Text File** adds a text file as a new node.
- **File → Export as Text** writes the selected node, its branch or the whole
  file as a numbered outline. **File → Print** shows a print preview.
- Files are saved in the Windows-compatible encoding when possible, so they
  stay readable by other programs that use the `.hjt` format.

### Options menu

| Option | Default |
|---|---|
| Open last file at startup | On |
| Keep a backup copy (`<file>.hjt.bak`) when saving: the file as it was when you opened it | On |
| Auto-save every 5 minutes | Off |

## Command line

```bash
twigpad [FILE]                 # open the window, optionally with a file
twigpad --dump FILE [--text]   # print a file's tree (and text) and exit
twigpad --version
```
