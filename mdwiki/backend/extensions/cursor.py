from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from markdown.util import etree


CURSOR_MARK = '%CURSOR%'
CURSOR_ID = '__CURSOR__'


class CursorExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.treeprocessors.add('cursor', CursorAnchorInjector(md), "<toc")


class CursorAnchorInjector(Treeprocessor):
    def run(self, root):
        parent_map = dict((c, p) for p in root.iter() for c in p)

        anchor = etree.Element('a')
        anchor.set('id', CURSOR_ID)

        # Iterate over all elements in the resulting HTML
        for child in root.iter():
            # If the child's inner text contains CURSOR_MARK
            # (e.g. <b>Hello CURSOR_MARK World</b>)
            if child.text and CURSOR_MARK in child.text:
                # If CURSOR_MARK is inside a link, just use its id instead of creating a new anchor
                # This may break some extensions
                if child.tag == 'a':
                    child.text = child.text.replace(CURSOR_MARK, '')
                    child.set('id', CURSOR_ID)
                else:
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
                        return root

                continue

            return root

        return root
