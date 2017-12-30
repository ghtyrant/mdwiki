from PyQt5.QtCore import QAbstractItemModel, QModelIndex, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog

from ..gui.new_article_ui import Ui_NewArticleDialog


class ArticleViewModel:
    def __init__(self, model, parent=None):
        self.model = model
        self.parentItem = parent

        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
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
        if self.parent:
            return self.parent.children.index(self)

        return 0

    def insertChildren(self, position, count, columns):
        if position < 0 or position > len(self.childItems):
            return False

        for row in range(count):
            data = [None for v in range(columns)]
            item = ArticleViewModel(data, self)
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
        if column == 0:
            if len(self.childItems) > 0:
                return QIcon.fromTheme('default-fileopen')
            else:
                return QIcon.fromTheme('application-document')
        elif column == 1:
            if self.model.modified:
                return QIcon.fromTheme('document-edit')
            else:
                return QIcon()
        elif column == 2:
            if self.model.has_unstaged_changes():
                return QIcon.fromTheme('dialog-warning')
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

    def setupModelData(self, wiki):
        def add_article(article, parent):
            for child in article.children:
                vm = ArticleViewModel(child, parent)
                parent.appendChild(vm)
                add_article(child, vm)

        add_article(wiki.get_root(), self.rootItem)


class NewArticleDialog(QDialog, Ui_NewArticleDialog):
    def __init__(self, parent, renderers):
        super().__init__(parent)

        self.setupUi(self)

        for file_type, renderer in renderers.items():
            self.type.addItem(QIcon(), renderer.name, renderer.file_type)

    def execute(self):
        return self.exec_()

    def get_data(self):
        return (self.name.text(), self.type.currentData())


class WikiTreeMixin:
    def setup_wiki_tree(self):
        self.ui.wikiTree.clicked.connect(self.item_clicked)
        self.ui.actionNewArticle.triggered.connect(
            self.show_new_article_dialog)
        self.current_article_index = None

    def item_clicked(self, index):
        article = self.ui.wikiTree.model().data(index, Qt.EditRole)
        self.current_article_index = index
        self.load_article(article)

    def show_new_article_dialog(self):
        dialog = NewArticleDialog(self, self.renderers)

        if dialog.execute() != QDialog.Accepted:
            return

        print(dialog.get_data())
