import re

from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from markdown.util import etree

CURSOR_MARK = '%CURSOR%'
CURSOR_ID = '__CURSOR__'


def split_path(path):
    """ Split a path string by separator in all components. """
    return path.strip('/').split('/')


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
            # If the child's inner text contains CURSOR_MARK
            # (e.g. <b>Hello CURSOR_MARK World</b>)
            if child.text and CURSOR_MARK in child.text:
                new_text = child.text[:child.text.find(CURSOR_MARK)]
                anchor.tail = child.text[child.text.find(
                    CURSOR_MARK) + len(CURSOR_MARK):]
                child.text = new_text
                child.insert(0, anchor)

            # If the text trailing the child contains CURSOR_MARK
            # (e.g. <b>Hello</b> World CURSOR_MARK)
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
                # Also check in the element's attributes (e.g. in href of <a>)
                for name, value in child.attrib.items():
                    if CURSOR_MARK in value:
                        child.set(name, value.replace(CURSOR_MARK, ''))
                        return None

                continue

            return None

        return None


def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    """ Taken from http://stackoverflow.com/a/16090640 """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s.decode("utf-8"))]
