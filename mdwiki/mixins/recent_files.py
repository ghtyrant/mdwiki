from PyQt5.QtCore import QFileInfo, QSettings
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction


class RecentFilesMixin:
    MAX_RECENT_FILES = 5

    def setup_recent_files(self):
        self.recent_wikis_actions = []
        self.setup_recent_wikis_menu()
        self.update_recent_wikis()

    def add_recent_wiki(self, path):
        settings = QSettings()
        files = settings.value('recentFileList', [])

        try:
            files.remove(path)
        except ValueError:
            pass

        files.insert(0, path)
        del files[RecentFilesMixin.MAX_RECENT_FILES:]

        settings.setValue('recentFileList', files)

    def setup_recent_wikis_menu(self):
        icon = QIcon.fromTheme("folder")

        for _ in range(RecentFilesMixin.MAX_RECENT_FILES):
            self.recent_wikis_actions.append(QAction(self, visible=False, icon=icon,
                                                     triggered=self.open_recent_wiki))

        for action in self.recent_wikis_actions:
            self.ui.menuRecentWikis.addAction(action)

    def update_recent_wikis(self):
        settings = QSettings()
        files = settings.value('recentFileList', [])

        num_recent_files = min(len(files), RecentFilesMixin.MAX_RECENT_FILES)

        for i in range(num_recent_files):
            text = "&%d %s" % (i + 1, QFileInfo(files[i]).fileName())
            self.recent_wikis_actions[i].setText(text)
            self.recent_wikis_actions[i].setData(files[i])
            self.recent_wikis_actions[i].setVisible(True)

        for j in range(num_recent_files, RecentFilesMixin.MAX_RECENT_FILES):
            self.recent_wikis_actions[j].setVisible(False)

    def open_recent_wiki(self):
        action = self.sender()
        if action:
            self.open_wiki(action.data())
