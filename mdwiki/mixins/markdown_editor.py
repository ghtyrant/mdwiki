import logging

from PyQt5.QtCore import (QFile,
                          QIODevice,
                          QTextStream,
                          pyqtSignal,
                          pyqtSlot,
                          QObject)
from PyQt5.QtGui import QFontDatabase, QDesktopServices
from PyQt5.Qsci import QsciLexerMarkdown, QsciLexerHTML, QsciScintilla
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel

from ..backend.markuprenderer import (MarkdownRenderer,
                                      PlainRenderer,
                                      ReSTRenderer)

logger = logging.getLogger(__name__)


class CustomWebPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navType, isMainFrame):
        if url.scheme() == 'qrc':
            return True

        QDesktopServices.openUrl(url)

        return False


class WebChannelProxy(QObject):
    link_clicked = pyqtSignal(str, name='linkClicked')

    @pyqtSlot(str)
    def activateLink(self, url):
        self.link_clicked.emit(url)


class MarkdownEditorMixin:
    SCROLLING_JS = """const element = document.getElementById('__CURSOR__');
        if (element !== null && element !== undefined) {
          const elementRect = element.getBoundingClientRect();
          const absoluteElementTop = elementRect.top + window.pageYOffset;
          const middle = absoluteElementTop - (window.innerHeight / 2);
          window.scrollTo(0, middle);
        }"""

    WEBCHANNEL_JS = """
    (function(){
        new QWebChannel(qt.webChannelTransport,
            function(channel) {
                var proxy = channel.objects.proxy;

                document.body.addEventListener('click', function (e) {
                    if (!e.target || e.target.nodeName != "A") {
                        return;
                    }
                    proxy.activateLink(e.target.getAttribute('href'));
                    e.preventDefault();
                }, false);
            }
        );
    })();"""

    def setup_markdown_editor(self):
        self.renderers = {}
        self.fallback_renderer = PlainRenderer()
        self.add_renderer(self.fallback_renderer)
        self.add_renderer(MarkdownRenderer())
        self.add_renderer(ReSTRenderer())

        # Set up Markdown editor
        lexer = QsciLexerMarkdown()
        fontdb = QFontDatabase()
        lexer.setDefaultFont(fontdb.font('Source Code Pro', 'Regular', 11))
        self.ui.markdownEditor.setLexer(lexer)
        self.ui.markdownEditor.setWrapMode(QsciScintilla.WrapWord)
        self.ui.markdownEditor.setMarginWidth(0, "0000")
        self.ui.markdownEditor.setMarginLineNumbers(0, True)
        self.ui.markdownEditor.setMarginsFont(
            fontdb.font('Source Code Pro', 'Regular', 11))
        self.ui.markdownEditor.setMarginType(0, QsciScintilla.NumberMargin)
        self.ui.markdownEditor.setIndentationsUseTabs(False)
        self.ui.markdownEditor.setTabWidth(2)
        self.ui.markdownEditor.setTabIndents(True)

        # Set up our custom page to open external links in a browser
        page = CustomWebPage(self)
        self.ui.markdownPreview.setPage(page)

        # Set up the web channel to intercept clicks on links
        channel = QWebChannel(self)
        self.channel_proxy = WebChannelProxy(self)
        channel.registerObject("proxy", self.channel_proxy)
        page.setWebChannel(channel)

        self.channel_proxy.link_clicked.connect(self.link_clicked)

        # Set up HTML preview
        self.ui.htmlPreview.setLexer(QsciLexerHTML())

        # Connect signals
        self.ui.actionUndo.triggered.connect(self.undo)
        self.ui.actionRedo.triggered.connect(self.redo)

        self.ui.actionSave.triggered.connect(self.save_article)
        self.ui.actionCommit.triggered.connect(self.commit_article)
        self.ui.actionEdit.toggled.connect(self.edit_toggled)

        # Load Github style
        style_file = QFile(':/styles/github.css')
        style_file.open(QIODevice.ReadOnly)
        self.style = QTextStream(style_file).readAll()
        style_file.close()

        self.current_article = None
        self.ui.markdownEditor.hide()

        self.ui.actionUndo.setEnabled(False)
        self.ui.actionRedo.setEnabled(False)

        self.update_toolbar()

    def link_clicked(self, url):
        article = self.get_current_wiki().get_root().resolve(url)

        if article is None:
            logger.warn('Link to %s could not be resolved!' % url)
            # TODO Let user create the article
            return

        self.load_article(article)

    def update_toolbar(self):
        self.ui.actionSave.setEnabled(False)
        self.ui.actionCommit.setEnabled(False)
        self.ui.uncommittedWarningLabel.hide()

        if self.current_article:

            if self.current_article.modified:
                self.ui.actionSave.setEnabled(True)

            if self.current_article.has_unstaged_changes():
                self.ui.actionCommit.setEnabled(True)
                self.ui.uncommittedWarningLabel.show()

            self.ui.wikiTree.model().updateItem(self.current_article_index)

    def edit_toggled(self, enabled):
        if enabled:
            self.ui.markdownEditor.show()
        else:
            self.ui.markdownEditor.hide()

    def add_renderer(self, renderer):
        self.renderers[renderer.get_file_type()] = renderer

    def text_changed(self):
        self.current_article.set_text(self.ui.markdownEditor.text())
        self.ui.actionUndo.setEnabled(True)

        self.update_toolbar()

    def cursor_changed(self, line, index):
        # Get the byte index of the cursor
        cursor_index = self.ui.markdownEditor.positionFromLineIndex(
            line, index)

        # Insert our cursor mark
        text = self.ui.markdownEditor.text()

        # Only jump to cursor when the editor is shown
        if self.ui.actionEdit.isChecked():
            new_text = text[:cursor_index] + '%CURSOR%'

            # TODO %CURSOR% breaks headings
            # if text[cursor_index:1] == '#':
            #     new_text += '\n'

            new_text += text[cursor_index:]

            text = new_text

        # Render and update the preview
        page = self.ui.markdownPreview.page()

        if self.current_article.file_type not in self.renderers:
            renderer = self.fallback_renderer
        else:
            renderer = self.renderers[self.current_article.file_type]

        html = renderer.render(text, style=self.style)

        # TODO this is an ugly hack! yuck!
        page.setHtml(
            html + """
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>(function() {%s\n%s})();</script>""" % (
                MarkdownEditorMixin.SCROLLING_JS,
                MarkdownEditorMixin.WEBCHANNEL_JS
            ))
        self.ui.htmlPreview.setText(html)

        # setHtml() steals focus from the editor - give it back
        self.ui.markdownEditor.setFocus()

    def load_article(self, article):
        # Disconnect any signals while changing article
        try:
            self.ui.markdownEditor.textChanged.disconnect(self.text_changed)
            self.ui.markdownEditor.cursorPositionChanged.disconnect(
                self.cursor_changed)
        except TypeError:
            pass

        # Select the article in the tree
        # (e.g. when we came here by clicking a link)
        self.select_article(article)

        self.current_article = article
        self.ui.markdownEditor.setText(article.get_text())

        self.update_toolbar()

        # Reconnect signals
        self.ui.markdownEditor.textChanged.connect(self.text_changed)
        self.ui.markdownEditor.cursorPositionChanged.connect(
            self.cursor_changed)

        # Disable Undo/Redo for newly loaded articles
        self.ui.actionUndo.setEnabled(False)
        self.ui.actionRedo.setEnabled(False)

        # Manually trigger rerendering of preview
        self.cursor_changed(0, 0)

    def save_article(self):
        self.current_article.write()
        self.update_toolbar()

    def commit_article(self):
        self.current_article.write()
        self.current_article.commit()
        self.update_toolbar()

    def undo(self):
        self.ui.markdownEditor.undo()
        self.ui.actionRedo.setEnabled(True)

        if not self.ui.markdownEditor.isUndoAvailable():
            self.ui.actionUndo.setEnabled(False)

    def redo(self):
        self.ui.markdownEditor.redo()

        if not self.ui.markdownEditor.isRedoAvailable():
            self.ui.actionRedo.setEnabled(False)
