from abc import ABC, abstractmethod
from functools import partial
import logging

import markdown
import pymdownx.emoji

logger = logging.getLogger(__name__)


class MarkupRenderer(ABC):
    def __init__(self, name, file_type):
        self.name = name
        self.file_type = file_type
        self.tree_iter = None

    @abstractmethod
    def render(self, raw_text, style=""):
        pass

    def get_file_type(self):
        return self.file_type


class PlainRenderer(MarkupRenderer):
    def __init__(self):
        super().__init__("Plaintext", ".txt")

    def render(self, raw_text, style=""):
        return raw_text


class MarkdownRenderer(MarkupRenderer):
    HTML_SKELETON = (
        '<!doctype HTML><html><head><meta charset="utf-8">'
        '<style type="text/css">%s</style></head><body>%s</body></html>'
    )

    MARKDOWN_EXTENSIONS = [
        'markdown.extensions.toc',
        'markdown.extensions.tables',
        'markdown.extensions.meta',
        'pymdownx.betterem',
        'pymdownx.tilde',
        'pymdownx.emoji',
        'pymdownx.tasklist',
        'pymdownx.superfences',
        'mdwiki.backend.extensions.mdwikilinks:WikiLinkExtension',
        'mdwiki.backend.extensions.cursor:CursorExtension'
    ]

    def __init__(self):
        super().__init__("Markdown", ".md")

    def url_exists(self, wiki, url):
        return wiki.get_article_by_url(url) is not None

    def render(self, wiki, raw_text, style=''):
        # BUG pymdownx.github fails to clean its state after each call, causing convert()
        # to use more and more resources with each call, slowing things down to a crawl
        # see https://github.com/facelessuser/pymdown-extensions/issues/15
        # e.g.: text = self.markdown.convert(raw_text)
        md = markdown.Markdown(extensions=MarkdownRenderer.MARKDOWN_EXTENSIONS,
                               extension_configs={
                                   "pymdownx.tilde": {
                                       "subscript": False
                                   },
                                   "markdown.extensions.toc": {
                                       "anchorlink": False
                                   },
                                   "pymdownx.emoji": {
                                       "emoji_index": pymdownx.emoji.gemoji,
                                       "emoji_generator": pymdownx.emoji.to_png,
                                       "alt": "short",
                                       "options": {
                                           "attributes": {
                                               "align": "absmiddle",
                                               "height": "20px",
                                               "width": "20px"
                                           },
                                           "image_path": "https://assets-cdn.github.com/images/icons/emoji/unicode/",
                                           "non_standard_image_path":
                                           "https://assets-cdn.github.com/images/icons/emoji/"
                                       }
                                   },
                                   "pymdownx.betterem": {
                                       "smart_enable": "all"
                                   },
                                   "mdwiki.backend.extensions.mdwikilinks:WikiLinkExtension": {
                                       "url_exists": partial(self.url_exists, wiki)
                                   }
                               })
        text = md.convert(raw_text)

        return MarkdownRenderer.HTML_SKELETON % (
            style,
            text
        )


class ReSTRenderer(MarkupRenderer):
    HTML_SKELETON = (
        '<!doctype HTML><html><head><meta charset="utf-8"></head><body>%s</body></html>'
    )

    def __init__(self):
        super().__init__("Restructured Text", ".rst")

    def render(self, raw_text, style=''):
        from docutils.core import publish_parts
        return ReSTRenderer.HTML_SKELETON % (
            publish_parts(raw_text, writer_name='html')['html_body']
        )
