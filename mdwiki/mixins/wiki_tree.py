from functools import partial

from PyQt5.QtCore import QAbstractItemModel, QModelIndex, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QMenu

from ..gui.new_article_ui import Ui_NewArticleDialog


class ArticleViewModel:
    def __init__(self, model, parent=None):
        self.model = model
        self.parentItem = parent

        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        print('model: %s self.child(%d) len: %d' % (
            'root' if not self.model else self.model.name, row, len(self.childItems)))
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
                return QIcon(':/icons/book.png')
            elif len(self.childItems) > 0:
                return QIcon(':/icons/blue-folder-open.png')
            else:
                return QIcon.fromTheme(':/icons/document-text-image.png')
        elif column == 1:
            if self.model.modified:
                return QIcon.fromTheme(':/icons/disk.png')
            else:
                return QIcon()
        elif column == 2:
            if self.model.has_unstaged_changes():
                return QIcon.fromTheme(':/icons/exclamation-circle.png')
            else:
                return QIcon()


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
        print('destinationChild: %d' % (self.rowCount(parent_index) + 1))
        self.beginMoveRows(old_parent_index, article_index.row(), article_index.row(), parent_index, self.rowCount(parent_index) - 1)
        self.endMoveRows()

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

        print(index)

        return None if not index else index[0]

    def setupModelData(self, wiki):
        def add_article(article, parent):
            article_vm = ArticleViewModel(article, parent)
            parent.appendChild(article_vm)

            for child in article.children:
                add_article(child, article_vm)

        add_article(wiki.get_root(), self.rootItem)


class NewArticleDialog(QDialog, Ui_NewArticleDialog):
    def __init__(self, parent, wiki_tree_model, renderers, article=None):
        super().__init__(parent)

        self.article = article

        self.setupUi(self)
        self.parent.setModel(wiki_tree_model)
        self.setup_ui_hacks()

        for _, renderer in renderers.items():
            self.type.addItem(QIcon(), renderer.name, renderer.file_type)

        if self.article is None:
            index = self.type.findData(wiki_tree_model.model.default_file_type)

            # Select wiki root
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
        return (self.name.text(), self.type.currentData(), parent_index, parent)

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
            # TODO this is ugly - the signal handler gets a bool as second argument, making article=bool
            partial(self.show_new_article_dialog, None))
        self.current_article_index = None

        self.ui.wikiTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.wikiTree.customContextMenuRequested.connect(
            self.show_context_menu)

    def item_clicked(self, index):
        article = self.ui.wikiTree.model().data(index, Qt.EditRole)
        self.current_article_index = index

        # TODO this fixes a crash when clicking on the wiki node
        # This should display some kind of index(?) (_index.md?)
        if article.parent is not None:
            self.load_article(article)

    def show_new_article_dialog(self, article=None):
        model = self.ui.wikiTree.model()
        dialog = NewArticleDialog(self, model, self.renderers, article)

        if dialog.execute() != QDialog.Accepted:
            return

        (name, file_type, parent_index, parent) = dialog.get_data()

        # Edit article
        if article:
            article.set_file_type(file_type)

            old_parent = article.parent
            article.move(name, parent)

            # Move article in tree
            if old_parent != parent:
                old_parent_index = model.findData(old_parent)
                article_index = model.findData(article)
                model.moveArticle(old_parent_index,
                                  article_index, parent_index)

        # New article
        else:
            new_article = parent.repository.create_article(name, file_type, parent)
            #new_article_vm = ArticleViewModel(new_article, parent_index)
            parent_vm = self.ui.wikiTree.model().getItem(parent_index)
            print(parent_vm.childCount())
            print(self.ui.wikiTree.model().insertArticle(self.ui.wikiTree.model().rowCount(parent_index), new_article, parent_index))
            #self.ui.wikiTree.model().setData()

    def show_context_menu(self, pos):
        index = self.ui.wikiTree.indexAt(pos)

        if index is None:
            return

        article = self.ui.wikiTree.model().data(index, Qt.EditRole)

        menu = QMenu()
        menu.addAction(self.ui.actionEditArticle)

        try:
            self.ui.actionEditArticle.triggered.disconnect()
        except TypeError:
            pass

        self.ui.actionEditArticle.triggered.connect(
            partial(self.show_new_article_dialog, article))

        menu.exec_(self.ui.wikiTree.viewport().mapToGlobal(pos))
