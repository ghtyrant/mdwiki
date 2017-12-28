import os
import re
from urllib.parse import urlparse

from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from markdown.util import etree

CURSOR_MARK = '%CURSOR%'
CURSOR_ID = '__CURSOR__'


def split_path(path):
    """ Split a path string by separator in all components. """
    head, tail = os.path.split(path)
    components = []

    while len(tail) > 0:
        components.insert(0, tail)
        head, tail = os.path.split(head)

    return components


def strip_file_scheme(path):
    result = urlparse(path)

    full_path = os.path.join(result.netloc, result.path)

    # On Win32, Gtk's folder chooser returns "file:///C:/yadda/yadda"
    # urlparse parses that to netloc="", path="/C:/yadda/yadda"
    # os.path.abspath turns that into "C:/C:/yadda/yadda"
    # That's why we remove a leading slash here
    if os.name == "nt" and full_path.startswith("/"):
        full_path = full_path[1:]

    return os.path.abspath(full_path)


class CursorExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.treeprocessors['cursor'] = CursorAnchorInjector(md)


class CursorAnchorInjector(Treeprocessor):
    def run(self, root):
        parent_map = {c: p for p in root.iter() for c in p}

        anchor = etree.Element('a')
        anchor.set('id', CURSOR_ID)

        # Iterate over all elements in the resulting HTML
        for child in root.iter():
            # If the child's inner text contains CURSOR_MARK (e.g. <b>Hello CURSOR_MARK World</b>)
            if child.text and CURSOR_MARK in child.text:
                new_text = child.text[:child.text.find(CURSOR_MARK)]
                anchor.tail = child.text[child.text.find(
                    CURSOR_MARK) + len(CURSOR_MARK):]
                child.text = new_text
                child.insert(0, anchor)

            # If the text trailing the child contains CURSOR_MARK (e.g. <b>Hello</b> World CURSOR_MARK)
            elif child.tail and CURSOR_MARK in child.tail:
                new_tail = child.tail[:child.tail.find(CURSOR_MARK)]
                anchor.tail = child.tail[child.tail.find(
                    CURSOR_MARK) + len(CURSOR_MARK):]
                child.tail = new_tail

                # Find out the id of the current child
                # This might be a bit inefficient, but it works
                parent = parent_map[child]
                for idx, elem in enumerate(parent):
                    if elem == child:
                        parent.insert(idx + 1, anchor)
                        break
            else:
                continue

            return None

        return None


def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    """ Taken from http://stackoverflow.com/a/16090640 """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s.decode("utf-8"))]
