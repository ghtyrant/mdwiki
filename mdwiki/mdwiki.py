from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QFileInfo, QSettings
from PyQt5.QtWidgets import QMainWindow, qApp, QAction

from .gui.mdwiki_ui import Ui_MainWindow


class MDWiki(QMainWindow, Ui_MainWindow):
    AUTHOR = 'skyr'
    APPLICATION = 'MDWiki'
    MAX_RECENT_FILES = 5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.recent_wikis_actions = []

        self.setupUi(self)
        self.setup_connections()
        self.setup_recent_wikis_menu()
        self.update_recent_wikis()

    def setup_connections(self):
        # Application Menu
        self.actionQuit.triggered.connect(qApp.quit)

    def open_recent_wiki(self):
        action = self.sender()
        if action:
            print(action.data())

    def set_current_wiki(self, path):
        settings = QSettings(MDWiki.AUTHOR, MDWiki.APPLICATION)
        files = settings.value('recentFileList', [])

        try:
            files.remove(path)
        except ValueError:
            pass

        files.insert(0, path)
        del files[MDWiki.MAX_RECENT_FILES:]

        settings.setValue('recentFileList', files)

    def setup_recent_wikis_menu(self):
        icon = QIcon.fromTheme("folder")

        for i in range(MDWiki.MAX_RECENT_FILES):
            self.recent_wikis_actions.append(QAction(self, visible=False, icon=icon,
                                                     triggered=self.open_recent_wiki))

        for action in self.recent_wikis_actions:
            self.menuRecentWikis.addAction(action)

    def update_recent_wikis(self):
        settings = QSettings(MDWiki.AUTHOR, MDWiki.APPLICATION)
        files = settings.value('recentFileList', [])

        num_recent_files = min(len(files), MDWiki.MAX_RECENT_FILES)

        for i in range(num_recent_files):
            text = "&%d %s" % (i + 1, QFileInfo(files[i]).fileName())
            print(text)
            self.recent_wikis_actions[i].setText(text)
            self.recent_wikis_actions[i].setData(files[i])
            self.recent_wikis_actions[i].setVisible(True)

        for j in range(num_recent_files, MDWiki.MAX_RECENT_FILES):
            print("%d is not visible" % j)
            self.recent_wikis_actions[j].setVisible(False)
