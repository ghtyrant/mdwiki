from PyQt5.QtWidgets import QDialog

from ..gui.new_article_ui import Ui_NewArticleDialog


class NewArticleDialog(QDialog, Ui_NewArticleDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setupUi(self)

    def execute(self):
        return self.exec_()


class WikiTreeMixin:
    def setup_wiki_tree(self):
        self.ui.wikiTree.itemClicked.connect(self.item_clicked)
        self.ui.actionNewArticle.triggered.connect(
            self.show_new_article_dialog)

    def item_clicked(self, item):
        self.load_article(item)

    def show_new_article_dialog(self):
        dialog = NewArticleDialog(self)

        if dialog.execute() != QDialog.Accepted:
            return
