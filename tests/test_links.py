# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from twigpad import links
from twigpad.links import FILE, MAIL, NODE, WEB
from twigpad.model import Document, Node


class LinkTests(unittest.TestCase):
    def test_find_links(self):
        text = ("See [http://example.com/a b] and www.site.org, "
                "mail [mailto:me@x.org] or \"file:///tmp/My File.txt\". "
                "Also [node://Notes/Recipes/Soup]. Not a link: [hello]")
        found = [link for _s, _e, link in links.iter_links(text)]
        self.assertEqual(found, ["http://example.com/a b", "www.site.org", "mailto:me@x.org",
                                 "file:///tmp/My File.txt", "node://Notes/Recipes/Soup"])

    def test_link_at_cursor_and_selection(self):
        text = "go to [www.example.com] now"
        self.assertEqual(links.link_at(text, 10), "www.example.com")
        self.assertEqual(links.link_at(text, 6), "www.example.com")   # on the bracket
        self.assertIsNone(links.link_at(text, 1))
        self.assertEqual(links.link_at("x http://a.b/c?d=1. y", 5), "http://a.b/c?d=1")
        sel = "file://C:/Program Files/app.exe"
        self.assertEqual(links.link_at("open " + sel, 2, selection=sel), sel)
        self.assertIsNone(links.link_at("plain", 2, selection="plain"))

    def test_classify(self):
        self.assertEqual(links.classify("www.a.org"), (WEB, "http://www.a.org"))
        self.assertEqual(links.classify("https://a.org"), (WEB, "https://a.org"))
        self.assertEqual(links.classify("mailto:x@y.z"), (MAIL, "mailto:x@y.z"))
        self.assertEqual(links.classify("file:///home/me/a.pdf"), (FILE, "/home/me/a.pdf"))
        self.assertEqual(links.classify("file://notes/a.txt"), (FILE, "notes/a.txt"))
        self.assertEqual(links.classify("NODE://Root/Child/"), (NODE, "Root/Child"))

    def test_resolve_node_path(self):
        doc = Document()
        root = doc.root.add_child(Node("My notes"))
        rec = root.add_child(Node("Recipes"))
        soup = rec.add_child(Node("Soup"))
        ab = root.add_child(Node("A/B testing"))
        deep = ab.add_child(Node("Results"))

        def find(path):
            return links.resolve_node(doc.top_nodes, path, lambda n: n.title, lambda n: n.children)

        self.assertIs(find("My notes/Recipes/Soup"), soup)
        self.assertIs(find("my NOTES/recipes"), rec)              # case is ignored
        self.assertIs(find("My notes/A/B testing/Results"), deep)  # title containing '/'
        self.assertIsNone(find("My notes/Nope"))
        self.assertIsNone(find(""))
        self.assertEqual(links.node_address(["My notes", "Recipes", "Soup"]),
                         "node://My notes/Recipes/Soup")


class SingleRootTests(unittest.TestCase):
    def test_wraps_several_top_nodes(self):
        doc = Document()
        doc.root.add_child(Node("A"))
        doc.root.add_child(Node("B"))
        self.assertTrue(doc.ensure_single_root("notes"))
        self.assertEqual([n.title for n in doc.top_nodes], ["notes"])
        self.assertEqual([n.title for n in doc.top_nodes[0].children], ["A", "B"])
        self.assertFalse(doc.ensure_single_root("x"))   # already single


if __name__ == "__main__":
    unittest.main()
