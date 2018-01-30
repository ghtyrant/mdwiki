import os
import sys
import logging

from PyQt5.QtCore import QCoreApplication, QIODevice, QTextStream, QFile
from PyQt5.QtWidgets import (QMainWindow,
                             qApp,
                             QFileDialog,
                             QMessageBox,
                             QApplication,
                             QStyleFactory)
from PyQt5.QtGui import QFontDatabase, QIcon

from .gui.mdwiki_ui import Ui_MainWindow

from .mixins.recent_files import RecentFilesMixin
from .mixins.markdown_editor import MarkdownEditorMixin
from .mixins.wiki_tree import WikiTreeMixin, WikiTreeModel
from .mixins.fullscreen_editor import FullscreenEditorMixin

from .backend.wiki import Wiki


class MDWiki(QMainWindow,
             RecentFilesMixin,
             MarkdownEditorMixin,
             WikiTreeMixin,
             FullscreenEditorMixin):
    ORG_NAME = 'skyr'
    ORG_DOMAIN = 'skyr.at'
    APP_NAME = 'MDWiki'

    def __init__(self, *args, **kwargs):
        QCoreApplication.setOrganizationName(MDWiki.ORG_NAME)
        QCoreApplication.setOrganizationDomain(MDWiki.ORG_DOMAIN)
        QCoreApplication.setApplicationName(MDWiki.APP_NAME)

        super().__init__(*args, **kwargs)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.setup_ui_hacks()
        self.setup_fonts()

        # Set up mixins
        self.setup_recent_files()
        self.setup_markdown_editor()
        self.setup_wiki_tree()
        self.setup_fullscreen_editor()

        self.setup_connections()

        self.current_wiki = None
        self.current_article_vm = None

    def setup_connections(self):
        # Application Menu
        self.ui.actionNewWiki.triggered.connect(self.reload_style)
        self.ui.actionQuit.triggered.connect(qApp.quit)
        self.ui.actionOpen.triggered.connect(self.show_open_wiki_dialog)

    def setup_ui_hacks(self):
        # Force equal division of QSplitter panes
        self.ui.editorSplitter.setSizes([sys.maxsize, sys.maxsize])

        self.setWindowIcon(QIcon(':/icons/app.png'))
        self.reload_style()

    def reload_style(self):
        style_file = QFile(':/style.css')
        style_file.open(QIODevice.ReadOnly)
        self.setStyleSheet(QTextStream(style_file).readAll())
        style_file.close()

    def setup_fonts(self):
        QFontDatabase.addApplicationFont(':/font/SourceCodePro-Regular.otf')
        QFontDatabase.addApplicationFont(':/font/SourceCodePro-It.otf')
        QFontDatabase.addApplicationFont(':/font/SourceCodePro-Bold.otf')

    def close_wiki(self):
        self.current_wiki.close()
        self.current_wiki = None

    def show_open_wiki_dialog(self):
        while True:
            path = str(QFileDialog.getExistingDirectory(
                self, 'Select Directory'))

            if path and not os.path.exists(os.path.join(path, '.git')):
                msg = 'This folder does not contain a valid wiki!'
                QMessageBox.information(self, 'Wrong path', msg)

                continue

            break

        if not path:
            return

        self.open_wiki(path)

    def set_current_wiki(self, wiki):
        self.current_wiki = wiki

    def get_current_wiki(self):
        return self.current_wiki

    def open_wiki(self, path):
        # If this wiki is already open, reopen it
        if self.current_wiki:
            self.close_wiki()

        wiki = Wiki.open(path)
        self.current_wiki = WikiTreeModel(['name', 'saved', 'unstaged'], wiki)

        self.ui.wikiTree.setModel(self.current_wiki)

        # Set column width of wiki tree
        self.ui.wikiTree.header().resizeSection(0, 250)
        self.ui.wikiTree.header().resizeSection(1, 24)
        self.ui.wikiTree.header().resizeSection(2, 24)

        name = wiki.name
        if not name:
            name = 'Unnamed'

        self.ui.wikiName.setText(name)

        self.add_recent_wiki(path)


def main():
    logging.basicConfig(
        format='[%(asctime)s] - %(name)s: (%(levelname)s) %(message)s', level=logging.DEBUG)
    logging.info("Starting up QMDWiki!")
    logging.info(QStyleFactory.keys())
    logging.getLogger("MARKDOWN").setLevel(logging.WARNING)

    # Use Fusion style
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))

    wiki = MDWiki()
    wiki.show()
    sys.exit(app.exec_())
