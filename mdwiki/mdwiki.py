import os
import sys
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QMainWindow, qApp, QFileDialog, QMessageBox

from .gui.mdwiki_ui import Ui_MainWindow

from .mixins.recent_files import RecentFilesMixin
from .mixins.markdown_editor import MarkdownEditorMixin
from .mixins.wiki_tree import WikiTreeMixin, WikiTreeModel

from .backend.wiki import Wiki

"""class ArticleViewModel(QTreeWidgetItem):
    def __init__(self, wiki_vm, article, parent, icon=None):
        super().__init__(parent, [article.get_name()])

        self.wiki_vm = wiki_vm
        self.model = article
        self.parent = parent

        if icon:
            self.setIcon(0, icon)
        elif self.model.children:
            self.setIcon(0, QIcon.fromTheme('default-fileopen'))
        else:
            self.setIcon(0, QIcon.fromTheme('application-document'))

        self.set_unstaged(self.model.has_unstaged_changes())

    def set_unstaged(self, flag):
        if flag:
            self.setIcon(2, QIcon.fromTheme('dialog-warning'))
        else:
            self.setIcon(2, QIcon())

    def set_unsaved(self, flag):
        if flag:
            self.setIcon(1, QIcon.fromTheme('document-edit'))
        else:
            self.setIcon(1, QIcon())


class WikiViewModel:
    def __init__(self, wiki, root):
        self.wiki = wiki
        self.setup_ui(root)

    def setup_ui(self, root):
        self.root_article_vm = ArticleViewModel(self,
                                                self.wiki.get_root(),
                                                root,
                                                QIcon.fromTheme('blue-folder-books'))

        self.add_children(self.root_article_vm)

    def add_children(self, root_article_vm):
        for child in root_article_vm.model.children:
            article_vm = ArticleViewModel(self, child, root_article_vm)
            self.add_children(article_vm)
"""


class MDWiki(QMainWindow, RecentFilesMixin, MarkdownEditorMixin, WikiTreeMixin):
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

        # Set up mixins
        self.setup_recent_files()
        self.setup_markdown_editor()
        self.setup_wiki_tree()

        self.setup_connections()

        self.wikis = {}
        self.current_article_vm = None

    def setup_connections(self):
        # Application Menu
        self.ui.actionQuit.triggered.connect(qApp.quit)
        self.ui.actionOpen.triggered.connect(self.open_wiki)

    def setup_ui_hacks(self):
        # Force equal division of QSplitter panes
        self.ui.splitter.setSizes([sys.maxsize, sys.maxsize])

    def close_wiki(self, wiki):
        self.ui.wikiTree.removeChild(wiki.item)
        del self.wikis[wiki.path]
        wiki.close()

    def show_open_wiki_dialog(self):
        path = str(QFileDialog.getExistingDirectory(self, 'Select Directory'))

        while True:
            if not os.path.exists(os.path.join(path, '.git')):
                QMessageBox.information(
                    self, 'Wrong path', 'This folder does not contain a valid wiki!')

                continue

            break

        if not path:
            return

        self.open_wiki(path)

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
