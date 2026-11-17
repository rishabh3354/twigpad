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
| Ctrl+Z | Undo the last change to the tree |
| Ctrl+Y or Ctrl+Shift+Z | Redo it |

### Undo in the tree

Changes to the tree can be undone, one step at a time: adding, deleting,
renaming, moving and dragging nodes, cut and paste, sorting, importing,
**Replace All**, and changing a node's icon or colour. Press **Ctrl+Z** in the
tree, or use **Edit → Undo**, which names what it will undo ("Undo Delete
“Projects”"). A deleted node comes back in the same place with everything
inside it: subnodes, articles, pictures, icons and the branches you had open.
Adding a node and typing its name counts as one step. Twigpad remembers the
last 200 changes until you open another file.

In the article, Ctrl+Z undoes typing as before: Undo always works on the pane
you are in. Right-click in the tree for Undo and Redo too.

**Node → Sort Whole Tree** sorts every level. You can also drag a node onto
another node (to put it inside) or between two nodes; hold **Shift** while
dropping onto a node to put it below that node instead of inside it. A slow
second click on the selected node renames it, like F2. **Ctrl+Up** and
**Ctrl+Down** scroll the tree without changing the selection, and
**Shift+F10** opens the right-click menu of the tree or the article.

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

**Edit → Insert → Text from File** inserts a text file at the cursor;
**File → Import → Text File into Article (Replace Its Text)** replaces the
whole article with a file (Ctrl+Z brings the old text back).

**Cut** and **Copy** work on the whole article when nothing is selected.
**Edit → Delete** deletes the selection, or, with nothing selected, the whole
article after asking. The article's right-click menu also has Find, Find
Next and Navigate → Go to Start / Go to End.

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

To add a language, choose **Options → Spelling Language → Download
Languages**. Pick one of about 50 languages (English, German, French, Spanish,
Italian, Portuguese, Russian, Dutch, Polish and many more) and press
**Download**: the dictionary is installed for you and used right away. The
same window removes dictionaries you downloaded. They are the free LibreOffice
and Mozilla dictionaries and are kept in `~/.local/share/hunspell`.

Twigpad also uses any Hunspell dictionaries installed on your system (such as
the `hunspell-de-de` package). Spell checking needs the Hunspell library
(`libhunspell`), which most desktops already have.

## View

- **Tree and Article**, **Tree Only** or **Article Only** chooses which panes
  are shown; Twigpad remembers the choice.
- **Expand / Collapse Selected Node** opens or closes one branch, one level or
  all levels deep; **Expand All** and **Collapse All** do the whole tree.
- Word wrap.
- **Fonts** chooses the font and size of the interface (menus, buttons and
  windows), the tree and the article, with a preview; changes show at once and
  **Restore Defaults** goes back to the original fonts. By default Twigpad uses
  a clean, easy-to-read font (Inter or Noto Sans when installed), with the tree
  and the article a little larger than the desktop's text. **Reset Fonts**
  puts back the default fonts and sizes.
- **Text Size**: **Ctrl+=** (or Ctrl++) makes the text larger and **Ctrl+-**
  smaller in the pane you are in; **Ctrl+0** goes back to the normal size.
  **Ctrl+mouse wheel** over the tree or the article does the same for that
  pane. The menu also has separate items for the tree and the article.
  Text that has its own size in a formatted note keeps that size. The tree's
  note icons grow and shrink with its text.
- **Tree Icon Size**: Small (the default), Medium, Large or Extra Large note
  icons in the tree; the rows and indentation grow with them.
- **Classic Tree Look** switches between the classic tree (folder icons,
  dotted lines, +/- boxes) and your desktop's standard tree style.
- **Theme**: **Light**, **Dark**, **Automatic** (light or dark, following your
  desktop's setting; the default) or **Desktop Style** (your desktop's own
  look and colours).
- **Language**: the language of the menus and windows. **Automatic** (the
  default) follows your desktop's language; or choose English, Deutsch,
  Français, Español, Italiano, Português (Brasil), Русский, 简体中文 or 日本語.
  Twigpad asks to restart to switch (it asks about unsaved changes first, and
  reopens the file you had open). Your notes are never translated. To try a
  language for one start only, run `twigpad --language de`.
- **Colours** sets the background and text colours of the tree and the
  article; **Restore Defaults** goes back to your desktop's colours.
- **Toolbars**: the classic five, in this order:

  | Toolbar | Buttons |
  |---|---|
  | File | New, Open, Save, Print, Options (opens the Options menu) |
  | Article Edit | Cut, Copy, Paste, Delete |
  | Tree Edit | Insert child node, insert node before, insert node after, delete node, rename node |
  | View | Find, Search Tree, Tree and Article / Tree Only / Article Only, Word Wrap |
  | Navigate | Follow Link, move node up / down / left / right, expand / collapse the selected branch |

  An **Extras** toolbar (undo, redo, bold, italic, focus) is off at first.
  **Icon Size** makes the toolbar icons Small, Medium, Large (the default) or
  Extra Large, and **Button Labels** shows each button's name beside or under
  its icon. When the toolbars no longer fit, they wrap onto more rows.
  Turn toolbars on or off here (or **Show All** / **Hide All**), or
  right-click the toolbar area. Drag a toolbar by its handle to move it, also
  to another side of the window. Twigpad remembers where they are.

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
| Shift+F11 | Search Tree (the whole tree, from anywhere) |
| Ctrl+R | Find and replace |
| F3 / Shift+F3 | Find next / previous |

**Ctrl+F** in the article searches the selected node. In the tree, Ctrl+F (or
**Search → Search Tree**, Shift+F11) opens the **Tree Search** window:

- Type the search text and press Enter or **Find**. Case does not matter.
- **What to search**: the **Total tree** or the **Subtree** of the selected
  node, in node titles (**Nodes**), **Articles**, or both.
- The results list every matching node with its number, title, where the
  text was found (**Node**, **Article** or **Article+Node**) and its path.
  **Maximum number of rows** limits the list (200 at first).
- Double-click a result, or press Enter, to select that node; the first match
  in its article is selected too. With **Hide search window after item is
  double clicked** on, the window then closes.
- **Search Article** selects the next match in the result's article each time
  you press it.

**Search → Find** (in the article) and **Replace** open the Find and Replace
window, which also has match case, whole words and regular expressions. Search looks in node
titles, articles, or both; in all nodes, the selected
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

### Crash recovery

While a file has unsaved changes, Twigpad quietly keeps a recovery copy of it,
updated every 30 seconds. If Twigpad crashes or the computer loses power, the
next start asks **Recover unsaved changes?**: **Recover** opens the changes
(Save then writes them to the original file), **Not Now** keeps the copy for
the next start, and **Discard Changes** deletes it. Saving, or closing the
window normally, deletes the copy. Copies of password-protected files stay
encrypted with the file's password. They are kept in
`~/.local/state/twigpad/recovery` (next to `twigpad.ini` in portable use).

### Moving to a new computer

**File → Backup & Restore → Back Up Notes and Settings** puts your notes files
(the open file and your recent files; untick any you don't want) and your
settings into one `.zip` file. Settings include the theme, fonts, toolbars,
colours, the words you added to the dictionary and the recent files list.
Password-protected files stay protected.

Copy the `.zip` to the new computer and choose **File → Backup & Restore →
Restore from Backup**. Twigpad shows where each file will go before it
changes anything: files go back to the same place in your home folder (or to
`Documents/Twigpad Restored` when that place doesn't exist there). Files that
are already on the computer are skipped and never overwritten, so restoring
twice is harmless. Recent files then point to the restored copies.

### Opening .hjt files from the file manager

**Options → Open .hjt Files with Twigpad** makes double-clicking a `.hjt` or
`.twig` file open it in Twigpad. Twigpad also offers this once, the first time
it starts. It only changes settings in your own home folder; to pick another
app later, right-click a file and use **Open With**. Packages (and the
Flatpak) set this up when they are installed.

### Options menu

| Option | Default |
|---|---|
| At Startup: Reopen the Last File, Ask Whether to Reopen It, Show the Quick Start Window (new file, open, or a recent file), or Start With a New File | Reopen |
| When Closing With Unsaved Changes: Ask Whether to Save, Save Automatically, or Don't Save | Ask |
| Keep a backup copy (`<file>.hjt.bak`) when saving: the file as it was when you opened it | On |
| Auto-save every 5 minutes | Off |
| Automatic Paste: text you copy in other programs is added to the end of the current article (for collecting snippets) | Off, not remembered |
| Use Tab to Switch Between Tree and Article: Tab switches panes and Ctrl+Tab types a tab in the article | Off |
| Minimize to Tray Instead of the Taskbar | Off |
| Keep Settings Next to the Program (see Portable use) | Off |

**Options → Reset All Settings to Defaults** puts every option, the theme,
fonts, text sizes, toolbars, colours and the window layout back to how they
were when Twigpad was installed, after asking first. Your notes files, the
recent files list and the words you added to the dictionary are kept.

### Portable use

To run Twigpad from a USB stick, turn on **Options → Keep Settings Next to
the Program**, or create an empty file called `twigpad.ini` next to the
AppImage (or the `twigpad` program). Twigpad then keeps its settings in that
file instead of your home folder. Turning the option off moves the settings
back and deletes the file.

## Help menu

- **Keyboard Shortcuts** (F1 or Ctrl+/) lists every shortcut, grouped by
  menu, with a search box.
- **Report a Bug** opens a new issue on Twigpad's GitHub page in your web
  browser. The form already lists your Twigpad, Qt, Python and Linux versions;
  describe what went wrong and submit it (you need a GitHub account). Nothing
  is sent until you submit it yourself.
- **Request a Feature** opens a new GitHub issue with a short form for your
  idea.
- **Support the Developer (Donate)** opens a PayPal page to support Twigpad.
- **More Apps by Warlord Softwares** lists other Linux apps by the same developer.
- **About the Developer** opens the developer's web page.
- **About Twigpad** shows the version, with the same links.

## Command line

```bash
twigpad [FILE]                 # open the window, optionally with a file
twigpad --language CODE        # menus in another language for this start (de, fr, ja, ...)
twigpad --dump FILE [--text]   # print a file's tree (and text) and exit
twigpad --version
```
