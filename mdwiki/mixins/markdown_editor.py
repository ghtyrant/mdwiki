from PyQt5.QtCore import QFile, QIODevice, QTextStream
from PyQt5.Qsci import QsciLexerMarkdown, QsciLexerHTML

from ..backend.markuprenderer import MarkdownRenderer, PlainRenderer, ReSTRenderer


class MarkdownEditorMixin:
    SCROLLING_JS = """<script>const element = document.getElementById('__CURSOR__');
        if (element !== null && element !== undefined) {
          const elementRect = element.getBoundingClientRect();
          const absoluteElementTop = elementRect.top + window.pageYOffset;
          const middle = absoluteElementTop - (window.innerHeight / 2);
          window.scrollTo(0, middle);
        }</script>"""

    def setup_markdown_editor(self):
        self.renderers = {}
        self.fallback_renderer = PlainRenderer()
        self.add_renderer(self.fallback_renderer)
        self.add_renderer(MarkdownRenderer())
        self.add_renderer(ReSTRenderer())
        self.ui.markdownEditor.setLexer(QsciLexerMarkdown())
        self.ui.htmlPreview.setLexer(QsciLexerHTML())

        self.ui.actionUndo.triggered.connect(self.undo)
        self.ui.actionRedo.triggered.connect(self.redo)

        self.ui.actionSave.triggered.connect(self.save_article)
        self.ui.actionCommit.triggered.connect(self.commit_article)
        self.ui.actionEdit.toggled.connect(self.edit_toggled)

        # Load Github style
        style_file = QFile(':/styles/github.css')
        style_file.open(QIODevice.ReadOnly)
        self.style = QTextStream(style_file).readAll()

        self.current_article_vm = None
        self.update_toolbar()
        self.ui.markdownEditor.hide()

        self.ui.actionUndo.setEnabled(False)
        self.ui.actionRedo.setEnabled(False)

    def update_toolbar(self):
        self.ui.actionSave.setEnabled(False)
        self.ui.actionCommit.setEnabled(False)
        self.ui.uncommittedWarningLabel.hide()

        if self.current_article_vm:
            self.current_article_vm.set_unsaved(False)
            self.current_article_vm.set_unstaged(False)

            if self.current_article_vm.model.modified:
                self.ui.actionSave.setEnabled(True)
                self.current_article_vm.set_unsaved(True)

            if self.current_article_vm.model.has_unstaged_changes():
                self.ui.actionCommit.setEnabled(True)
                self.ui.uncommittedWarningLabel.show()
                self.current_article_vm.set_unstaged(True)

    def edit_toggled(self, enabled):
        if enabled:
            self.ui.markdownEditor.show()
        else:
            self.ui.markdownEditor.hide()

    def add_renderer(self, renderer):
        self.renderers[renderer.get_file_type()] = renderer

    def text_changed(self):
        self.current_article_vm.model.set_text(self.ui.markdownEditor.text())
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
        if self.current_article_vm.model.file_type not in self.renderers:
            renderer = self.fallback_renderer
        else:
            renderer = self.renderers[self.current_article_vm.model.file_type]

        html = renderer.render(text, style=self.style)
        page.setHtml(html + MarkdownEditorMixin.SCROLLING_JS)
        self.ui.htmlPreview.setText(html)

        # setHtml() steals focus from the editor - give it back
        self.ui.markdownEditor.setFocus()

    def load_article(self, article_vm):
        # Disconnect any signals while changing article
        try:
            self.ui.markdownEditor.textChanged.disconnect(self.text_changed)
            self.ui.markdownEditor.cursorPositionChanged.disconnect(
                self.cursor_changed)
        except TypeError:
            pass

        self.current_article_vm = article_vm
        self.ui.markdownEditor.setText(article_vm.model.get_text())

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
        self.current_article_vm.model.write()
        self.update_toolbar()

    def commit_article(self):
        self.current_article_vm.model.write()
        self.current_article_vm.model.commit()
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
