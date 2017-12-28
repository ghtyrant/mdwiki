import sys
from PyQt5.QtWidgets import QApplication

from .mdwiki import MDWiki

if __name__ == '__main__':
    app = QApplication(sys.argv)
    wiki = MDWiki()
    wiki.show()
    sys.exit(app.exec_())
