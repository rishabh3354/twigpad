# The `.hjt` file format

Notes for contributors. The reader and writer live in `src/twigpad/hjt.py`.

## Layout

A `.hjt` file is plain text. A version line comes first, then one block per
node, in tree order (depth-first, parents before children):

```
<Treepad version 2.7>
dt=Text
<node>
Node title
0
First line of the article
Second line of the article
<end node> 5P9i0s8y19Z
dt=Text
<node>
A child node
1
<end node> 5P9i0s8y19Z
```

| Line | Meaning |
|---|---|
| `<Treepad version X>` | File header. Very old files use `<hj-Treepad version 0.9>`. |
| `dt=Text` | Article type. `dt=RTF` marks a formatted article; missing in old files. |
| `<node>` | Start of a node. |
| title | One line. |
| level | Depth of the node: `0` is top level, `1` its child, and so on. |
| article lines | Zero or more lines, kept exactly. |
| `<end node> 5P9i0s8y19Z` | End of the node. Old files use a bare `<end node>`. |

The token after `<end node>` exists so an article line reading `<end node>`
is not mistaken for the end marker. When a file uses the token, Twigpad only
accepts the full `<end node> 5P9i0s8y19Z` line as the end.

## Encoding and line endings

Files written on Windows use the ANSI code page (cp1252) and CRLF line
endings. Twigpad reads UTF-8 (with or without a byte-order mark), UTF-16 with
a byte-order mark, cp1252, and falls back to Latin-1.

When saving, Twigpad writes `<Treepad version 2.7>`, CRLF line endings and
cp1252, switching to UTF-8 only when the text contains characters cp1252
cannot store.

## Repairs when reading

The reader recovers as much as it can and records each problem in
`Document.warnings`:

- missing header: read as an old-format file;
- stray lines between nodes: skipped;
- a level that skips depths (for example 0 then 3): attached to the nearest
  possible parent;
- a level line that is not a number: node placed at top level;
- an unterminated last node (truncated file): its text is kept;
- `dt=RTF` articles: converted to plain text (`src/twigpad/rtf.py`).

`.zip` files are searched for the first member that reads as a `.hjt` file.
