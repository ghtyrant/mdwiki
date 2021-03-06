import logging
from functools import partial

from PyQt5.QtCore import QAbstractItemModel, QModelIndex, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QMenu, QMessageBox, QHeaderView

from ..gui.new_article_ui import Ui_NewArticleDialog

logger = logging.getLogger(__name__)


ICON_WIKI = 'accessories-dictionary.png'
ICON_CATEGORY = 'blue-folder-open.png'
ICON_ARTICLE = 'document-text-image.png'
ICON_UNSAVED = 'disk.png'
ICON_UNCOMMITTED = 'exclamation-circle.png'


class ArticleViewModel:
    def __init__(self, model, parent=None):
        self.model = model
        self.parentItem = parent

        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        if row >= len(self.childItems):
            return None

        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 3

    def childNumber(self):
        if self.parentItem is not None:
            return self.parentItem.childItems.index(self)
        return 0

    def data(self, column):
        if column == 0:
            return self.model

        return None

    def parent(self):
        return self.parentItem

    def row(self):
        if self.model.parent:
            return self.model.parent.children.index(self)

        return 0

    def insertChild(self, position, model):
        if position < 0 or position > len(self.childItems):
            return False

        item = ArticleViewModel(model, self)
        self.childItems.insert(position, item)

        return True

    def insertChildren(self, position, count, columns):
        if position < 0 or position > len(self.childItems):
            return False

        for row in range(count):
            item = ArticleViewModel(None, self)
            self.childItems.insert(position, item)

        return True

    def removeChildren(self, position, count):
        if position < 0 or position > len(self.childItems):
            return False

        for row in range(count):
            self.childItems.pop(position)

        return True

    def setData(self, column, value):
        if column != 0:
            return False

        self.model = value

        return True

    def decorationIcon(self, column):
        if not self.model:
            return QIcon()

        if column == 0:
            if not self.model.parent:
                return QIcon(':/icons/%s' % ICON_WIKI)
            elif len(self.childItems) > 0:
                return QIcon(':/icons/%s' % ICON_CATEGORY)
            else:
                return QIcon(':/icons/%s' % ICON_ARTICLE)
        elif column == 1:
            if self.model.modified:
                return QIcon(':/icons/%s' % ICON_UNSAVED)
            else:
                return QIcon()
        elif column == 2:
            if self.model.has_unstaged_changes():
                return QIcon(':/icons/%s' % ICON_UNCOMMITTED)
            else:
                return QIcon()

    def __repr__(self):
        return self.model.pretty_name


class WikiTreeModel(QAbstractItemModel):
    def __init__(self, headers, wiki, parent=None):
        super(WikiTreeModel, self).__init__(parent)

        self.model = wiki
        self.rootItem = ArticleViewModel(None)
        self.setupModelData(wiki)

    def columnCount(self, parent=QModelIndex()):
        return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        item = self.getItem(index)

        if role == Qt.DisplayRole:
            if index.column() == 0:
                return item.data(index.column()).name
        elif role == Qt.EditRole:
            return item.data(index.column())
        elif role == Qt.DecorationRole:
            return item.decorationIcon(index.column())
        else:
            return None

    def close(self):
        self.model.close()

    def flags(self, index):
        if not index.isValid():
            return 0

        return Qt.ItemIsSelectable | super(WikiTreeModel, self).flags(index)

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item

        return self.rootItem

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section)

        return None

    def index(self, row, column, parent=QModelIndex()):
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()

        parentItem = self.getItem(parent)
        childItem = parentItem.child(row)

        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def insertColumns(self, position, columns, parent=QModelIndex()):
        self.beginInsertColumns(parent, position, position + columns - 1)
        success = self.rootItem.insertColumns(position, columns)
        self.endInsertColumns()

        return success

    def insertRows(self, position, rows, parent=QModelIndex()):
        parentItem = self.getItem(parent)
        self.beginInsertRows(parent, position, position + rows - 1)
        success = parentItem.insertChildren(position, rows,
                                            self.rootItem.columnCount())
        self.endInsertRows()

        return success

    def insertArticle(self, position, article, parent=QModelIndex()):
        parentItem = self.getItem(parent)
        self.beginInsertRows(parent, position, position)
        success = parentItem.insertChild(position, article)
        self.endInsertRows()

        return success

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        # TODO this crashes when deleting an item
        # getItem() returns a tuple (<NULL>,) - probably some internal Qt shit
        childItem = self.getItem(index)
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.childNumber(), 0, parentItem)

    def removeColumns(self, position, columns, parent=QModelIndex()):
        self.beginRemoveColumns(parent, position, position + columns - 1)
        success = self.rootItem.removeColumns(position, columns)
        self.endRemoveColumns()

        if self.rootItem.columnCount() == 0:
            self.removeRows(0, self.rowCount())

        return success

    def removeRows(self, position, rows, parent=QModelIndex()):
        parentItem = self.getItem(parent)

        self.beginRemoveRows(parent, position, position + rows - 1)
        success = parentItem.removeChildren(position, rows)
        self.endRemoveRows()

        return success

    def moveArticle(self, old_parent_index, article_index, parent_index):
        # This should actually use beginMoveRows/endMoveRows
        # But since documentation is seriously lacking and there are no
        # examples on how to correctly use those let's just be fools
        article = self.getItem(article_index)
        newParent = self.getItem(parent_index)

        self.removeRows(article_index.row(), 1, old_parent_index)
        self.insertArticle(newParent.childCount(), article.model, parent_index)

    def rowCount(self, parent=QModelIndex()):
        parentItem = self.getItem(parent)

        return parentItem.childCount()

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole:
            return False

        item = self.getItem(index)
        result = item.setData(index.column(), value)

        if result:
            self.dataChanged.emit(index, index)

        return result

    def setHeaderData(self, section, orientation, value, role=Qt.EditRole):
        if role != Qt.EditRole or orientation != Qt.Horizontal:
            return False

        result = self.rootItem.setData(section, value)
        if result:
            self.headerDataChanged.emit(orientation, section, section)

        return result

    def updateItem(self, index):
        index_left = self.index(index.row(), 0, index.parent())
        index_right = self.index(
            index.row(), self.columnCount() - 1, index.parent())

        self.dataChanged.emit(index_left, index_right)

    def findData(self, data):
        index = self.match(self.index(0, 0),
                           Qt.EditRole,
                           data,
                           2,
                           Qt.MatchRecursive)

        return None if not index else index[0]

    def setupModelData(self, wiki):
        def add_article(article, parent):
            article_vm = ArticleViewModel(article, parent)
            parent.appendChild(article_vm)

            for child in article.children:
                add_article(child, article_vm)

        add_article(wiki.root, self.rootItem)


class NewArticleDialog(QDialog, Ui_NewArticleDialog):
    def __init__(self, parent, wiki_tree_model,
                 renderers, article=None, selected_index=None):
        super().__init__(parent)

        self.article = article

        self.setupUi(self)
        self.parent.setModel(wiki_tree_model)
        self.setup_ui_hacks()

        for _, renderer in renderers.items():
            self.type.addItem(QIcon(), renderer.name, renderer.file_type)

        if self.article is None:
            index = self.type.findData(wiki_tree_model.model.default_file_type)
            self.type.setCurrentIndex(index)

            # Select wiki root
            if selected_index:
                self.parent.setCurrentIndex(selected_index)
            else:
                self.parent.setCurrentIndex(wiki_tree_model.index(0, 0))
        else:
            index = self.type.findData(article.file_type)
            self.name.setText(self.article.name)

            # Find parent article in tree model
            parent_index = wiki_tree_model.findData(article.parent)

            self.parent.setCurrentIndex(parent_index)

        if index == -1:
            return

        self.type.setCurrentIndex(index)

    def setup_ui_hacks(self):
        self.parent.hideColumn(1)
        self.parent.hideColumn(2)
        self.parent.expandAll()

    def execute(self):
        return self.exec_()

    def get_data(self):
        parent_index = self.parent.currentIndex()
        parent = self.parent.model().data(parent_index, Qt.EditRole)
        return (self.name.text(), self.type.currentData(),
                parent_index, parent)

    def done(self, res):
        if res != QDialog.Accepted:
            super().done(res)

            return

        if not self.name.text().strip():
            return

        if self.parent.currentIndex() is None:
            return

        super().done(res)


class WikiTreeMixin:
    def setup_wiki_tree(self):
        self.ui.wikiTree.clicked.connect(self.item_clicked)
        self.ui.actionNewArticle.triggered.connect(
            # TODO this is ugly
            # The signal handler gets a bool as second argument
            # making article=bool
            partial(self.show_new_article_dialog, None))
        self.current_article_index = None

        self.ui.wikiTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.wikiTree.customContextMenuRequested.connect(
            self.show_context_menu)

    def setup_wiki_tree_ui_hacks(self):
        # TODO This is weird. The next line causes the wiki to silently
        # crash when it is in setup_wiki_tree(). Putting it here
        # seems to work
        self.ui.wikiTree.header().setSectionResizeMode(0, QHeaderView.Stretch)

    def item_clicked(self, index):
        article = self.ui.wikiTree.model().data(index, Qt.EditRole)
        if article is None:
            logger.warning('Could not get selected article!')
            return

        self.current_article_index = index

        # TODO this fixes a crash when clicking on the wiki node
        # This should display some kind of index(?) (_index.md?)
        # if article.parent is not None:
        self.set_current_wiki(article.wiki)
        self.load_article(article)

        self.setup_wiki_tree_ui_hacks()

    def select_article(self, article):
        index = self.ui.wikiTree.model().findData(article)

        if index:
            self.ui.wikiTree.setCurrentIndex(index)
        else:
            logger.warn('Could not select article %s: Not found!' % (article))

    def show_delete_article_dialog(self, article):
        message = "This will delete the article '%s'" % (article.name)
        if len(article.children) > 0:
            message += ", including it's children:\n\n - %s\n" % (
                '\n - '.join([str(c) for c in article.children]))
        message += "\nAre you sure?"

        reply = QMessageBox.question(self, 'Delete Article',
                                     message, QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            model = self.ui.wikiTree.model()
            article_index = model.findData(article)
            model.removeRows(article_index.row(), 1, article_index.parent())
            article.delete()
            self.load_article(self.current_wiki.root)

    def show_new_article_dialog(self, article=None):
        model = self.ui.wikiTree.model()
        dialog = NewArticleDialog(self, model, self.renderers,
                                  article, self.ui.wikiTree.currentIndex())

        if dialog.execute() != QDialog.Accepted:
            return

        (name, file_type, parent_index, parent) = dialog.get_data()

        # Edit article
        if article:
            article.file_type = file_type

            old_parent = article.parent
            article.move(name, parent)

            # Move article in tree
            if old_parent != parent:
                article_index = model.findData(article)
                model.moveArticle(article_index.parent(),
                                  article_index, parent_index)

            self.load_article(article)

        # New article
        else:
            new_article = parent.wiki.create_article(name,
                                                     file_type, parent)
            self.ui.wikiTree.model().insertArticle(
                self.ui.wikiTree.model().rowCount(parent_index),
                new_article,
                parent_index)

    def show_context_menu(self, pos):
        index = self.ui.wikiTree.indexAt(pos)

        if index is None:
            return

        article = self.ui.wikiTree.model().data(index, Qt.EditRole)

        menu = QMenu()
        menu.addAction(self.ui.actionEditArticle)
        menu.addSeparator()
        menu.addAction(self.ui.actionDeleteArticle)

        # TODO Add action to insert link to this article in the current editor

        try:
            self.ui.actionEditArticle.triggered.disconnect()
            self.ui.actionDeleteArticle.triggered.disconnect()
        except TypeError:
            pass

        self.ui.actionEditArticle.triggered.connect(
            partial(self.show_new_article_dialog, article))

        self.ui.actionDeleteArticle.triggered.connect(
            partial(self.show_delete_article_dialog, article))

        menu.exec_(self.ui.wikiTree.viewport().mapToGlobal(pos))
