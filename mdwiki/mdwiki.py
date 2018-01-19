import os
import sys
import logging

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import (QMainWindow,
                             qApp,
                             QFileDialog,
                             QMessageBox,
                             QApplication,
                             QStyleFactory)
from PyQt5.QtGui import QFontDatabase, QIcon, QPalette, QColor

from .gui.mdwiki_ui import Ui_MainWindow

from .mixins.recent_files import RecentFilesMixin
from .mixins.markdown_editor import MarkdownEditorMixin
from .mixins.wiki_tree import WikiTreeMixin, WikiTreeModel

from .backend.wiki import Wiki


class MDWiki(QMainWindow,
             RecentFilesMixin,
             MarkdownEditorMixin,
             WikiTreeMixin):
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

        self.setup_connections()

        self.wikis = {}
        self.current_wiki = None
        self.current_article_vm = None

    def setup_connections(self):
        # Application Menu
        self.ui.actionQuit.triggered.connect(qApp.quit)
        self.ui.actionOpen.triggered.connect(self.show_open_wiki_dialog)

    def setup_ui_hacks(self):
        # Force equal division of QSplitter panes
        self.ui.splitter.setSizes([sys.maxsize, sys.maxsize])

        self.setWindowIcon(QIcon(':/icons/app.png'))

    def setup_fonts(self):
        QFontDatabase.addApplicationFont(':/font/SourceCodePro-Regular.otf')
        QFontDatabase.addApplicationFont(':/font/SourceCodePro-It.otf')
        QFontDatabase.addApplicationFont(':/font/SourceCodePro-Bold.otf')

    def close_wiki(self, wiki):
        self.ui.wikiTree.removeChild(wiki.item)
        del self.wikis[wiki.path]
        wiki.close()

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
        if path in self.wikis:
            self.close_wiki(self.wikis[path])

        wiki = Wiki.open(path)
        self.wikis[path] = WikiTreeModel(['name', 'saved', 'unstaged'], wiki)

        self.ui.wikiTree.setModel(self.wikis[path])

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
    logging.basicConfig(level=logging.DEBUG)
    logging.info("Starting up QMDWiki!")
    logging.info(QStyleFactory.keys())

    # Use Fusion style
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))

    # TODO This is not how it should be done. Replace this with a proper style.
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))

    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))

    app.setPalette(dark_palette)

    app.setStyleSheet(
        """QToolTip {
            color: #ffffff;
            background-color: #2a82da;
            border: 1px solid white;
        }""")

    wiki = MDWiki()
    wiki.show()
    sys.exit(app.exec_())
