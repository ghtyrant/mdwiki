import os
from abc import ABC, abstractmethod
import markdown

from .constants import APP_DATA_BASE_PATHS
from .util import CursorExtension


class MarkupRenderer(ABC):
    def __init__(self, name, file_type, language_id="plain"):
        self.name = name
        self.file_type = file_type
        self.language_id = language_id
        self.tree_iter = None

    @abstractmethod
    def render(self, raw_text):
        pass

    def get_tree_iter(self):
        return self.tree_iter

    def set_tree_iter(self, tree_iter):
        self.tree_iter = tree_iter

    def get_name(self):
        return self.name

    def get_file_type(self):
        return self.file_type

    def get_language_id(self):
        return self.language_id


class PlainRenderer(MarkupRenderer):
    def __init__(self):
        super().__init__("Plaintext", ".txt", "plain")

    def render(self, raw_text):
        return raw_text


class MarkdownRenderer(MarkupRenderer):
    HTML_SKELETON = (
        '<!doctype HTML><html><head><meta charset="utf-8">'
        '<style type="text/css">%s</style></head><body>%s</body></html>'
    )

    MARKDOWN_EXTENSIONS = [
        'pymdownx.github',
        'markdown.extensions.toc',
        CursorExtension()
    ]

    def __init__(self):
        super().__init__("Markdown", ".md", "markdown")

        self.markdown = markdown.Markdown(
            extensions=MarkdownRenderer.MARKDOWN_EXTENSIONS,
            extension_configs={
                "pymdownx.tilde": {
                    "subscript": False
                },
                "pymdownx.betterem": {
                    "smart_enable": "all"
                }
            })

        self.style = ""
        for path in APP_DATA_BASE_PATHS:
            full_path = os.path.join(path, "styles", "github.css")

            if not os.path.exists(full_path):
                continue

            print("Loading style 'github' from path %s" % (full_path))

            with open(full_path, "r") as stream:
                self.style = stream.read()
                break

        if not self.style:
            print("Could not load style 'github.css'!")

    def render(self, raw_text):
        # BUG pymdownx.github fails to clean its state after each call, causing convert()
        # to use more and more resources with each call, slowing things down to a crawl
        # see https://github.com/facelessuser/pymdown-extensions/issues/15
        # e.g.: text = self.markdown.convert(raw_text)
        md = markdown.Markdown(extensions=MarkdownRenderer.MARKDOWN_EXTENSIONS)
        text = md.convert(raw_text)
        return MarkdownRenderer.HTML_SKELETON % (
            self.style,
            text
        )


class ReSTRenderer(MarkupRenderer):
    HTML_SKELETON = (
        '<!doctype HTML><html><head><meta charset="utf-8"></head><body>%s</body></html>'
    )

    def __init__(self):
        super().__init__("Restructured Text", ".rst", "rest")

    def render(self, raw_text):
        from docutils.core import publish_parts
        return ReSTRenderer.HTML_SKELETON % (
            publish_parts(raw_text, writer_name='html')['html_body']
        )
