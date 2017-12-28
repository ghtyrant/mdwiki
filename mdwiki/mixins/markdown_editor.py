from ..backend.markuprenderer import MarkdownRenderer

from PyQt5.Qsci import QsciLexerMarkdown


class MarkdownEditorMixin:
    def setup_markdown_editor(self):
        self.renderer = MarkdownRenderer()
        self.ui.markdownEditor.setLexer(QsciLexerMarkdown())

        self.ui.markdownEditor.textChanged.connect(self.text_changed)

        self.ui.markdownPreview.loadFinished.connect(
            self.preview_load_finished)

    def text_changed(self):
        print('TEXT CHANGED!')
        print(self.ui.markdownEditor.text())
        position = self.ui.markdownEditor.getCursorPosition()
        cursor_index = self.ui.markdownEditor.positionFromLineIndex(*position)
        text = self.ui.markdownEditor.text()
        text = text[:cursor_index] + '%CURSOR%' + text[cursor_index + 1:]
        self.ui.markdownPreview.setHtml(self.renderer.render(text))
        self.ui.markdownEditor.setFocus()

    def load_article(self, article_vm):
        self.current_article_vm = article_vm
        self.ui.markdownEditor.setText(article_vm.model.get_text())
        print(article_vm.model.get_name())

    def preview_load_finished(self, ok):
        self.ui.markdownPreview.page().runJavaScript("""
        const element = document.getElementById('""" + '__CURSOR__' + """');
        if (element !== null && element !== undefined) {
          const elementRect = element.getBoundingClientRect();
          const absoluteElementTop = elementRect.top + window.pageYOffset;
          const middle = absoluteElementTop - (window.innerHeight / 2);
          window.scrollTo(0, middle);
        }""")
