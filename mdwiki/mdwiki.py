import os
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, qApp, QFileDialog, QMessageBox, QTreeWidgetItem

from .gui.mdwiki_ui import Ui_MainWindow

from .mixins.recent_files import RecentFilesMixin
from .mixins.markdown_editor import MarkdownEditorMixin

from .backend.wiki import Wiki


class ArticleViewModel(QTreeWidgetItem):
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


class MDWiki(QMainWindow, RecentFilesMixin, MarkdownEditorMixin):
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

        self.setup_recent_files()
        self.setup_markdown_editor()
        self.setup_connections()

        self.wikis = {}
        self.current_article_vm = None

    def setup_connections(self):
        # Application Menu
        self.ui.actionQuit.triggered.connect(qApp.quit)
        self.ui.actionOpen.triggered.connect(self.open_wiki)

        self.ui.wikiTree.itemClicked.connect(self.item_clicked)

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

        self.wikis[path] = WikiViewModel(Wiki.open(path), self.ui.wikiTree)

        self.add_recent_wiki(path)

    def item_clicked(self, item):
        self.load_article(item)
