import sys

from PyQt5.QtWidgets import QMainWindow

from .markdown_editor import CustomWebPage
from ..gui.fullscreen_ui import Ui_FullscreenWindow


class FullscreenEditorMixin:
    def setup_fullscreen_editor(self):
        # Set up fullscreen window
        self.fullscreenUi = Ui_FullscreenWindow()
        self.fullscreenWindow = QMainWindow()
        self.fullscreenUi.setupUi(self.fullscreenWindow)

        # Hide on the start
        self.hide_fullscreen_editor()

        # Splitter should give both widgets 50%
        self.fullscreenUi.splitter.setSizes([sys.maxsize, sys.maxsize])

        # Set up markdown editor
        self.setup_scintilla(self.fullscreenUi.markdownEditor)

        # Set up preview
        page = CustomWebPage(self)
        self.fullscreenUi.markdownPreview.setPage(page)

        # Set up the web channel to intercept clicks on links
        page.setWebChannel(self.ui.markdownPreview.page().webChannel())
        self.fullscreenUi.markdownPreview.setPage(page)

        # Connect signals
        self.fullscreenUi.actionCloseFullscreen.triggered.connect(
            self.hide_fullscreen_editor)

    def show_fullscreen_editor(self):
        self.fullscreenUi.markdownEditor.setText(self.ui.markdownEditor.text())
        self.fullscreenUi.markdownEditor.textChanged.connect(
            self.update_editor_text)
        self.fullscreenUi.markdownEditor.cursorPositionChanged.connect(
            self.set_editor_cursor)
        self.fullscreenWindow.showNormal()
        self.fullscreenWindow.showFullScreen()

    def hide_fullscreen_editor(self):
        # In case textChanged is not connected, we simply do nothing
        try:
            self.fullscreenUi.markdownEditor.textChanged.disconnect(
                self.update_editor_text)
            self.fullscreenUi.markdownEditor.cursorPositionChanged.disconnect(
                self.set_editor_cursor)
        except TypeError:
            pass

        self.fullscreenWindow.hide()

    def update_editor_text(self):
        self.ui.markdownEditor.setText(self.fullscreenUi.markdownEditor.text())

    def set_editor_cursor(self, line, index):
        # Get the byte index of the cursor
        cursor_index = self.fullscreenUi.markdownEditor.positionFromLineIndex(
            line, index)

        self.render_text(self.fullscreenUi.markdownEditor,
                         self.fullscreenUi.markdownPreview, cursor_index)

        self.ui.markdownEditor.setCursorPosition(line, index)
