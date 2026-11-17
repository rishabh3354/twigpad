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

### Focus and tabs

- **View → Focus on Branch** (Ctrl+]) shows only the selected note and the
  notes inside it. **Focus Out One Level** (Ctrl+[) goes up a level, and
  **Show Whole Tree** shows everything again. While focused, the focused note
  works like the top note. Jumping to a note outside the branch (from Find, a
  link or a backlink) shows the whole tree again.
- **View → Open Branch in New Tab** (Ctrl+T) opens the selected branch in a
  tab of its own above the tree. Each tab remembers the note selected in it.
  Ctrl+PgDown / Ctrl+PgUp switch tabs; Ctrl+W closes one. The tab bar appears
  once there is more than one tab.

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

## Formatted notes

Notes start as plain text. Use any command in the top part of the **Format**
menu and the note becomes a *formatted note*:

| Command | Key |
|---|---|
| Bold, Italic, Underline | Ctrl+B, Ctrl+I, Ctrl+U |
| Strikethrough, Text Colour, Highlight Colour, Font | |
| Larger / Smaller Text | Ctrl+Shift+. / Ctrl+Shift+, |
| Paragraph Style: Normal Text, Heading 1-3 | Ctrl+0, Ctrl+1, Ctrl+2, Ctrl+3 |
| Alignment, Bulleted List, Numbered List | |
| Insert → Picture, Table, Horizontal Line | |
| Table → Insert Row / Column, Delete Row / Column | |
| Clear Formatting (of the selected text) | |
| Convert Note to Plain Text | |

Pasting a picture (a screenshot, an image copied in a viewer) also makes the
note formatted. In plain notes, pasted text loses its formatting, as before.
Search, links, tags, spelling and word count work in formatted notes too.

Formatted notes, pictures, note icons and colours, and passwords are saved in
**Twigpad notes files (`.twig`)**. A `.hjt` file holds plain text only, so
when you save a `.hjt` file that uses any of these, Twigpad asks whether to
save it as `.twig` (keeps everything) or as a plain `.hjt` (keeps the text).
Your `.hjt` file is never changed unless you choose plain `.hjt`.

## Note icons and colours

Right-click a note and choose **Icon and Colour** (also in the **Node**
menu): pick an icon (folder, page, star, flag, done, important, information,
heart, bookmark, idea) and a colour for the title and icon. Saved in `.twig`
files.

## Password protection

**File → Set Password** encrypts the file. It is saved as a `.twig` file,
encrypted with AES-256; Twigpad asks for the password when you open it.
**File → Remove Password** saves it unencrypted from then on. The status bar
shows *Password protected* while a protected file is open.

**If you forget the password, the notes cannot be recovered.** Backup copies
(`.bak`) of a protected file are protected with the same password; Twigpad
never keeps an unencrypted backup of it. When you protect a `.hjt` file, it is
saved as a new `.twig` file and the original `.hjt` stays as it was: delete it
if it should stay private.

## Tags, backlinks and word count

- **Tags**: write `#` followed by a word anywhere in a title or article, for
  example `#todo` or `#work-project`. Tags are shown in green. **View →
  Panels → Tags** (Ctrl+Shift+G) lists every tag with the number of notes;
  click a tag to see its notes, and click a note to go to it. Case does not
  matter: `#Todo` and `#todo` are the same tag.
- **Backlinks**: **View → Panels → Backlinks** (Ctrl+Shift+B) lists the notes
  that link to the selected one with a `[node://…]` link.
- **Word count**: the status bar shows the words in the article, or in the
  selection. **Edit → Word Count** also counts the note with its subnotes and
  the whole file.

## Spelling

Misspelled words are underlined in red. Right-click one for suggestions, or
**Add to Dictionary** to stop it being marked. Turn it off with **Options →
Check Spelling**, and choose the dictionary under **Options → Spelling
Language**. Words in capitals, links and tags are not checked.

Spell checking uses the Hunspell dictionaries installed on your system. To add
a language, install its dictionary package, for example `hunspell-de-de` on
Debian and Ubuntu or `hunspell-de` on Fedora.

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

- **Open** accepts `.twig` and `.hjt` files, backup copies (`.bak`, `.hjt~`)
  and `.zip` archives that contain a `.hjt` file. Backups are opened as a new unsaved
  file, so **Save** asks for a new name instead of overwriting the backup.
- Damaged or cut-off files are opened as far as possible; a message lists
  what was repaired.
- **File → Import → Tree File or Backup** adds every node of another file
  inside the selected node, for combining several files into one.
- **File → Import → Text Files** adds one or more text files, each as a new
  node. **CSV File** adds a node per row: the first column is the title, the
  other columns become the article.
- **File → Export** writes the selected node, its branch or the whole file as
  a numbered text outline or as an HTML web page with a table of contents
  (formatted notes and pictures included).
  **Selected Node and Subnodes as Tree File** saves a branch as its own `.hjt`
  file; **as Twigpad File** saves it as `.twig` with its formatting (and the
  same password, if the file has one).
- **File → Print** shows a print preview of the selected branch, the selected
  node only, or the whole file.
- **File → Read Only** protects the file from changes. Files you don't have
  permission to change are opened read only; **Save** then asks for a new name.
- **File → Minimize to Tray** (Ctrl+M) hides the window to the system tray;
  click the tray icon to bring it back. Without a tray it minimizes normally.
- If another program changes the open file, Twigpad asks whether to reload
  it. If you keep your version, or the file was deleted, **Save** writes your
  version. Saving over changes made elsewhere always asks first.
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
