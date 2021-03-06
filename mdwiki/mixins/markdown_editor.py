import logging
import re

from PyQt5.QtCore import (QFile,
                          QIODevice,
                          QTextStream,
                          pyqtSignal,
                          pyqtSlot,
                          QObject,
                          QEvent,
                          Qt)

from PyQt5.QtGui import QFontDatabase, QDesktopServices
from PyQt5.QtWidgets import QMessageBox, QWidget
from PyQt5.Qsci import QsciLexerMarkdown, QsciLexerHTML, QsciScintilla, QsciAPIs
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QUrl

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


class QsciAPIWiki(QsciAPIs):
    def updateAutoCompletionList(self, context, options):
        return ['ballowallo', 'balloquallo', 'ballomallo']

    def autoCompletionSelected(self, *args, **kwargs):
        return super().autoCompletionSelected(*args, **kwargs)


class MarkdownEditorMixin:
    SCROLLING_JS = """const element = document.getElementById('__CURSOR__');
        if (element !== null && element !== undefined) {
          const elementRect = element.getBoundingClientRect();
          const absoluteElementTop = elementRect.top + window.pageYOffset;
          const middle = absoluteElementTop - (window.innerHeight / 2);
          setTimeout(function () {window.scrollTo(0, middle);}, 2);
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

                    let href = e.target.getAttribute('href');

                    if (href[0] == '#')
                        return;

                    proxy.activateLink(href);
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
        self.setup_lexer()
        self.setup_scintilla(self.ui.markdownEditor)

        # Set up our custom page to open external links in a browser
        page = CustomWebPage(self)
        self.ui.markdownPreview.setPage(page)
        QWebEngineSettings.globalSettings().setAttribute(
            QWebEngineSettings.FocusOnNavigationEnabled, False)
        # self.ui.markdownPreview.

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
        self.ui.actionFullscreen.triggered.connect(self.show_fullscreen_editor)
        self.ui.actionAutoLink.triggered.connect(self.auto_link_word)
        self.ui.actionAutoLinkAll.triggered.connect(self.auto_link_all)

        self.ui.markdownEditor.installEventFilter(self)

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

    def eventFilter(self, widget, event):
        if event.type() == QEvent.ShortcutOverride and widget is self.ui.markdownEditor:
            if event.key() == Qt.Key_L and event.modifiers() & Qt.ControlModifier:
                event.ignore()
                return True

        return QWidget.eventFilter(self, widget, event)

    def setup_lexer(self):
        fontdb = QFontDatabase()
        self.lexer = QsciLexerMarkdown()
        self.lexer.setDefaultFont(fontdb.font(
            'Source Code Pro', 'Regular', 11))
        # TODO autocompletion of links does not work
        self.api = QsciAPIWiki(self.lexer)
        self.api.prepare()

    def setup_scintilla(self, widget):
        # Set up Markdown editor
        fontdb = QFontDatabase()
        widget.setWrapMode(QsciScintilla.WrapWord)
        widget.setMarginWidth(0, "0000")
        widget.setMarginLineNumbers(0, True)
        widget.setMarginsFont(fontdb.font('Source Code Pro', 'Regular', 11))
        widget.setMarginType(0, QsciScintilla.NumberMargin)
        widget.setIndentationsUseTabs(False)
        widget.setTabWidth(2)
        widget.setTabIndents(True)
        widget.setEolMode(QsciScintilla.EolUnix)

        widget.setAutoCompletionSource(QsciScintilla.AcsAPIs)
        widget.setAutoCompletionThreshold(1)
        widget.setAutoCompletionCaseSensitivity(False)
        widget.setAutoCompletionReplaceWord(False)
        widget.setAutoCompletionWordSeparators([' '])
        # widget.setAutoCompletionUseSingle(QsciScintilla.AcusNever)

        widget.setLexer(self.lexer)

    def link_clicked(self, url):
        article = self.current_wiki.root.resolve(url)

        if article is None:
            logger.info('Link to %s could not be resolved!' % url)
            msg = "The article '%s' does not exist yet! Do you want to create it?" % url
            reply = QMessageBox.question(self, 'Create Article',
                                         msg, QMessageBox.Yes, QMessageBox.No)

            if reply == QMessageBox.Yes:
                article = self.current_wiki.create_article_by_url(
                    url, self.current_wiki.default_file_type)
                parent_index = self.ui.wikiTree.model().findData(article.parent)
                self.ui.wikiTree.model().insertArticle(
                    self.ui.wikiTree.model().rowCount(parent_index),
                    article,
                    parent_index)
            else:
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
            self.update_wordcount()
            self.ui.actionAutoLink.setEnabled(True)
            self.ui.actionAutoLinkAll.setEnabled(True)
        else:
            self.ui.markdownEditor.hide()
            self.statusBar().showMessage("")
            self.ui.actionAutoLink.setEnabled(False)
            self.ui.actionAutoLinkAll.setEnabled(False)

    def add_renderer(self, renderer):
        self.renderers[renderer.get_file_type()] = renderer

    def text_changed(self):
        self.current_article.text = self.ui.markdownEditor.text()
        self.ui.actionUndo.setEnabled(True)
        self.update_wordcount()
        self.update_toolbar()

        line, index = self.ui.markdownEditor.getCursorPosition()
        cursor_index = self.ui.markdownEditor.positionFromLineIndex(
            line, index)

        if self.ui.markdownEditor.text()[cursor_index - 1:cursor_index + 1] == '[[':
            self.ui.markdownEditor.autoCompleteFromAPIs()

    def render_text(self, text_widget, preview_widget, cursor_index):
        text = text_widget.text()

        # Only jump to cursor when the editor is shown
        if self.ui.actionEdit.isChecked():
            # Prevent CURSOR_MARK from breaking headings
            if text[cursor_index:cursor_index + 1] == '#' or text[cursor_index - 1:cursor_index] == '#':
                cursor_index = text.find(' ', cursor_index) + 1

            new_text = text[:cursor_index] + '%CURSOR%'
            new_text += text[cursor_index:]

            text = new_text

        if self.current_article.file_type not in self.renderers:
            renderer = self.fallback_renderer
        else:
            renderer = self.renderers[self.current_article.file_type]

        html = renderer.render(
            self.current_article.wiki, text, style=self.style)

        html = html + """
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>(function() {%s\n%s})();</script>""" % (
            MarkdownEditorMixin.SCROLLING_JS,
            MarkdownEditorMixin.WEBCHANNEL_JS
        )

        # Render and update the preview
        url = QUrl(self.current_article.wiki.physical_path + '/')
        preview_widget.page().setHtml(html, url)
        self.ui.htmlPreview.setText(html)

    def auto_link_word(self):
        if self.ui.markdownEditor.hasSelectedText():
            word = self.ui.markdownEditor.selectedText()
        else:
            text = self.ui.markdownEditor.text()
            line, index = self.ui.markdownEditor.getCursorPosition()
            cursor_position = self.ui.markdownEditor.positionFromLineIndex(
                line, index)
            word_start = text.rfind(' ', 0, cursor_position)
            word_end = text.find(' ', cursor_position)
            word_end_line = text.find("\n", cursor_position)

            if word_end_line < word_end:
                word_end = word_end_line

            word = text[word_start + 1:word_end]

        article = self.current_wiki.find_article_by_name(word)

        if article:
            if self.ui.markdownEditor.hasSelectedText():
                self.ui.markdownEditor.replaceSelectedText(
                    "[[%s]]" % (article.wiki_url))
            else:
                line, index_start = self.ui.markdownEditor.lineIndexFromPosition(
                    word_start + 1)
                _, index_end = self.ui.markdownEditor.lineIndexFromPosition(
                    word_end)
                self.ui.markdownEditor.setSelection(
                    line, index_start, line, index_end)

                self.ui.markdownEditor.replaceSelectedText(
                    "[[%s]]" % (article.wiki_url))

                self.ui.markdownEditor.setCursorPosition(line, index)
        else:
            logger.info("Could not find article '%s'" % (word))

    def auto_link_all(self):
        # TODO Allow user to select root-article
        # e.g., only auto link to articles in a certain category
        text = self.ui.markdownEditor.text().split('\n')
        for name, article in self.current_wiki.get_name_dict().items():
            for line_index, line in enumerate(text):

                # Skip headlines
                if line.startswith('#'):
                    continue

                offset = 0
                for match in re.finditer(name + r'(?![^\[]*\])', line):
                    link = "[[%s]]" % (article.wiki_url)
                    line = line[:match.start()] + link + line[match.end():]

                    offset += len(link) - len(name)

                text[line_index] = line

        self.ui.markdownEditor.setText('\n'.join(text))

    def cursor_changed(self, line, index):
        # Get the byte index of the cursor
        cursor_index = self.ui.markdownEditor.positionFromLineIndex(
            line, index)

        self.render_text(self.ui.markdownEditor,
                         self.ui.markdownPreview, cursor_index)

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
        self.ui.markdownEditor.setText(article.text)

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

    def update_wordcount(self):
        text = self.ui.markdownEditor.text()
        text_start = 0
        if text.startswith("---\n"):
            text_start = text.find('\n---\n') + 4
        count = len(re.findall(r'\w+', text[text_start:]))
        self.statusBar().showMessage('Words: %d' % (count))

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
