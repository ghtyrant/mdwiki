import os
import sys
from enum import IntEnum


class ArticleStoreColumns(IntEnum):
    NAME = 0
    OBJECT = 1
    ICON = 2
    STATUS_ICON = 3
    SENSITIVE = 4


class HistoryStoreColumns(IntEnum):
    NAME = 0
    OBJECT = 1


class AvailableRendererStoreColumns(IntEnum):
    EXTENSION = 0
    NAME = 1


SEARCH_ICON_DISCARD = 'dialog-close'

DEFAULT_FILE_PERMISSION = 0o0644
DEFAULT_FOLDER_PERMISSION = 0o0755

APP_DATA_BASE_PATHS = [
    "/usr/share/mdwiki/",
    "/usr/local/share/mdwiki",
    os.getcwd()
]

if hasattr(sys, 'frozen'):
    APP_DATA_BASE_PATHS.append(sys._MEIPASS)

INDEX_FILE_NAME = "_index"
CONFIG_FILE_NAME = ".wikiconfig"

DEFAULT_ARTICLE_HTML = """
<html><body><h1>mdwiki</h1></body></html>
"""

FALLBACK_RENDERER = ".txt"
