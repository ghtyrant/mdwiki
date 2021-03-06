import os
import shutil
import time
import logging
import re

from dulwich.file import GitFile
from slugify import slugify

from .util import split_path
from .constants import DEFAULT_FOLDER_PERMISSION, INDEX_FILE_NAME

ICON_FOLDER = 'folder-symbolic'
ICON_ARTICLE = 'folder-documents-symbolic'
ICON_wiki = 'accessories-dictionary'

ICON_STATUS_CHANGES = 'dialog-warning'

logger = logging.getLogger(__name__)


class ArticleHistoryEntry:
    def __init__(self, article, commit):
        self.article = article
        self.commit = commit
        self.sha = commit.id.decode('utf-8')
        self.author = commit.author.decode('utf-8')
        self.committer = commit.committer.decode('utf-8')
        self.author_time = commit.author_time
        self.commit_time = commit.commit_time

    def get_lines(self):
        """ Returns the article's content in this past commit. """
        git_repos = self.article.wiki.git_repository

        object_store = git_repos.object_store
        old_tree = self.commit.tree

        new_tree = git_repos[git_repos.head()].tree

        old_lines = []
        changes = object_store.tree_changes(old_tree, new_tree)
        for (oldpath, newpath), (_, _), (oldsha, _) in changes:
            if not newpath or not oldpath:
                continue

            if (newpath.decode('utf-8') == self.article.physical_path
                    and oldpath.decode('utf-8') == self.article.physical_path):

                if oldsha:
                    old_object = object_store[oldsha]
                    old_lines = old_object.as_raw_string().decode('utf-8').splitlines(keepends=True)

                    break

        if old_lines and not old_lines[-1].endswith('\n'):
            old_lines[-1] += '\n'

        return old_lines


class Article:
    def __init__(self, wiki, parent, file_type, is_directory=False, name=None, file_name=None):
        self._file_name = file_name if file_name else slugify(name)
        self._file_type = file_type
        self.parent = parent
        self.wiki = wiki
        self.is_directory = is_directory

        self.children = []
        self.history = []
        self.links = []

        self._text = None
        self.modified = False

        self.changed_files = set()

        if self.parent:
            self.parent.add_child(self)

        if file_name is None:
            self.text = "# " + name
            self.write()
            self.commit(message="Initial commit for '%s'" %
                        (self.wiki_url))
        else:
            # TODO the ugliest of all hacks!
            # This triggers a read from the file which in turn sets self._name
            self.text

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Article '%s'>" % self.name

    def is_root(self):
        return self.parent is None

    def is_category(self):
        return self.is_directory

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        line_end = self.text.find('\n')
        if line_end == -1:
            line_end = len(self.text)

        self.text = '# ' + name + self.text[line_end:]
        self._name = name

    def refresh_name(self):
        if self._text.startswith('#'):
            line_end = self._text.find('\n')
            if line_end == -1:
                line_end = len(self._text)

            self._name = self._text[2:line_end].strip()
        else:
            self._name = self._file_name

    @property
    def text(self):
        if self._text is None:
            self._text = self.read()
            self.refresh_name()
            self.refresh_links()

        return self._text

    @text.setter
    def text(self, text):
        if text == self._text:
            return

        self.modified = True

        # Force Unix style line endings
        self._text = text.replace('\r\n', '\n').replace('\r', '\n')
        self.refresh_name()
        self.refresh_links()

    @property
    def file_name(self):
        if self.is_category():
            return self._file_name

        return self._file_name + self.file_type

    @property
    def file_type(self):
        return self._file_type

    @file_type.setter
    def file_type(self, file_type):
        if file_type == self._file_type:
            return

        old_physical_path = self.physical_path

        if self.is_category():
            old_physical_path = self.index_file_name

        self.add_changed_file(old_physical_path)
        self.file_type = file_type

        new_physical_path = self.physical_path

        if self.is_category():
            new_physical_path = self.index_file_name

        os.rename(os.path.join(self.wiki.physical_path, old_physical_path),
                  os.path.join(self.wiki.physical_path, new_physical_path))
        self.add_changed_file(new_physical_path)
        self.commit("Changed file type of '%s' to '%s'" %
                    (self.wiki_url, self.file_type))

        self._file_type = file_type

    @property
    def index_file_name(self):
        if self.is_category():
            return INDEX_FILE_NAME + self.file_type

        return ""

    @property
    def wiki_url(self):
        """ This returns the URL of this article, relative to the root of the wiki.
        e.g. 'test/article'
        """
        if not self.is_root():
            slash = '/' if not self.parent.is_root() else ''
            return self.parent.wiki_url + slash + self.name
        else:
            # We don't want to add the name of the wiki to the link
            return ''

    @property
    def absolute_physical_path(self):
        """ This returns the absolute, physical path to either the file or the folder of this article. """
        return os.path.join(self.wiki.physical_path, self.physical_path)

    @property
    def physical_path(self):
        """ This returns the relative, physical path to either the file or the folder of this article. """
        if not self.is_root():
            return os.path.join(self.parent.physical_path, self.file_name)
        else:
            return ""

    def export(self, output_path, renderers):
        target_path = os.path.join(output_path, self.physical_path)

        if self.is_directory:
            target_path = os.path.join(target_path, 'index.html')
        else:
            target_path = os.path.splitext(target_path)[0] + '.html'

        target_dir = os.path.dirname(target_path)

        if self.wiki.root != self:
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)

            with open(target_path, 'wb') as stream:
                renderer = renderers[self.file_type]
                stream.write(renderer.render(self.text.encode('utf-8')))

        for child in self.children:
            child.export(target_dir, renderers)

    def refresh_links(self):
        links = re.findall(r'\[\[([^\[\]|]*)[^\[\]]*\]\]', self.text)

        self.links = []
        for link in links:
            article = self.wiki.get_article_by_url(link.replace(':', '/'))

            if article:
                self.links.append(article)

    def add_child(self, article):
        """ This adds a child to this article, turning it into a category if it isn't one already. """
        # This is the first child, convert to category!
        if not (self.has_children() or self.is_category()):
            self.convert_to_folder()

        self.children.append(article)

    def remove_child(self, article):
        self.children.remove(article)

        # Convert back to a file once we have no more children and are not root
        if not self.has_children() and self.is_category() and not self.is_root():
            self.convert_to_file()

    def find_by_name(self, name):
        if self.name.lower() == name.lower():
            return self

        for child in self.children:
            article = child.find_by_name(name)

            if article:
                return article

    def get_child_by_name(self, name):
        for child in self.children:
            if child.name.lower() == name.lower():
                return child

        return None

    def get_child_by_file_name(self, file_name):
        for child in self.children:
            if child.file_name.lower() == file_name.lower():
                return child

        return None

    def get_all_physical_paths(self):
        files = []

        if self.is_category():
            files.append(os.path.join(self.physical_path,
                                      self.index_file_name))
        else:
            files.append(self.physical_path)

        for child in self.children:
            files += child.get_all_physical_paths()

        return files

    def has_children(self):
        return len(self.children) > 0

    def move(self, name=None, parent=None):
        # TODO this method still has bugs, sometimes renamed files are not committed
        if parent is None:
            parent = self.parent

        if name is None:
            name = self.name

        if parent == self:
            raise ValueError("Can't be parent of myself!")

        # Nothing changed? Nothing to do then!
        if slugify(name) == self._file_name and parent == self.parent:
            logger.info("Moved called, but nothing changed!")
            return

        # Store current paths for later use
        old_wiki_url = self.wiki_url
        old_physical_path = self.physical_path
        old_absolute_physical_path = self.absolute_physical_path

        if parent != self.parent:
            self.add_changed_files(self.get_all_physical_paths())

        # Change our name
        self._file_name = slugify(name)

        # If this is simply a rename, add the old and the new name to the commit
        if parent == self.parent:
            self.add_changed_file(old_physical_path)
            self.add_changed_file(self.physical_path)

        if parent != self.parent:
            # If the new parent isn't a folder yet, convert it
            if not parent.is_category():
                parent.convert_to_folder()

        new_path = os.path.join(
            parent.absolute_physical_path, self.file_name)

        # This will move & rename this article
        shutil.move(old_absolute_physical_path, new_path)

        if parent != self.parent:
            # Remove ourself from the old parent
            self.parent.remove_child(self)

            # ... and add us to the new one
            self.parent = parent
            self.parent.add_child(self)

            self.add_changed_files(self.get_all_physical_paths())

        self.commit(message="Moved '%s' to '%s'." %
                    (old_wiki_url, self.wiki_url))

    def convert_to_folder(self):
        """This function turns an article file into a folder, keeping its content.
        e.g. from 'test.md' to 'test' (directory) and '/test/_index.md' (file)
        """
        # This points to '/test.md'
        physical_path = self.absolute_physical_path

        self.add_changed_file(self.physical_path)

        # Remove the file extension to get the path to the new folder
        new_folder_path = os.path.splitext(physical_path)[0]

        # Create the folder
        os.mkdir(new_folder_path, DEFAULT_FOLDER_PERMISSION)

        # Move and rename the old file (e.g. from '/test.md' to '/test/_index.md')
        self.is_directory = True
        new_index_file = os.path.join(
            new_folder_path, self.index_file_name)
        os.rename(physical_path, new_index_file)

        # The new file_name will the name of the folder, so simply remove the file extension
        self.add_changed_file(os.path.join(
            self.physical_path, self.index_file_name))

        # Commit the new file and the old one, so git knows we have moved it
        self.commit("Turned '%s' into a category." % (self.wiki_url))

    def convert_to_file(self):
        """This function does the opposite of convert_to_folder().
        e.g. from 'test/_index.md' (folder + file) to 'test.md'
        """
        # This points to '/test'
        physical_path = self.absolute_physical_path

        # This points to '/test/_index.md'
        index_file_path = os.path.join(physical_path, self.index_file_name)
        self.add_changed_file(os.path.join(
            self.physical_path, self.index_file_name))

        # Add the file extension to get the new file name ('/test' becomes '/test.md')
        new_file_path = physical_path + self.file_type

        # Move and rename the index file
        os.rename(index_file_path, new_file_path)

        # Remove the old directory - this should be guaranteed to be empty, because
        # we only get called when this article has no more children
        # TODO Catch the error in case it is NOT empty and handle it gracefully
        os.rmdir(physical_path)

        # Store the old index file path before we change our file_name
        old_index_path = os.path.join(
            self.physical_path, self.index_file_name)

        # Simply add the file extension to the current file name

        # Committhe old index file ...
        self.add_changed_file(self.physical_path)

        # ... turn ourselves back into a file ...
        self.is_directory = False

        # ... and commit the new file
        self.add_changed_file(self.physical_path)
        self.commit("Turned '%s' into an article." %
                    (self.wiki_url), [old_index_path])

    def has_unstaged_changes(self):
        """ Return wether this article has changes that haven't been committed yet. """
        physical_path = self.physical_path

        if self.is_category():
            physical_path = os.path.join(
                physical_path, self.index_file_name)

        return self.wiki.is_path_unstaged(physical_path)

    def resolve(self, url):
        """ Recursively resolve a wiki url. """

        # For convenience, the user can call this function with a string (e.g. '/test/category/article')
        # We will turn it into a list for him (e.g. ['test', 'category', 'article'])
        if isinstance(url, str):
            url = split_path(url)

        if len(url) == 0:
            return self

        # Pop the next part of the url
        name = url.pop(0)

        # Is this one of our children?
        article = self.get_child_by_name(name)

        # No -> we can't resolve this URL
        if article is None:
            return None

        # If there are parts in the path left, hand it over to our children
        if len(url) > 0:
            return article.resolve(url)

        # else, we have found our target, return it
        else:
            return article

    def create_article_from_file(self, path):
        name, file_type = os.path.splitext(path)

        if not file_type:
            file_type = '.md'

        self.create_article_by_url(name, file_type)

    def create_article_by_url(self, url, file_type):
        """ Create an article and all categories in between. Works similar to resolve(). """

        # For convenience, the user can call this function with a string (e.g. '/test/category/article')
        # We will turn it into a list for him (e.g. ['test', 'category', 'article'])
        if isinstance(url, str):
            url = split_path(url)

        file_name = url.pop(0)
        article = self.get_child_by_file_name(file_name)

        if article is None:
            article = Article(self.wiki,
                              self,
                              file_type,
                              is_directory=len(url) > 0,
                              file_name=file_name)

        if len(url) > 0:
            return article.create_article_by_url(url, file_type)
        else:
            return article

    def delete(self, commit=True):
        """ This deletes this article, its files on disk and recursively all of its descendants. """
        all_physical_paths = self.get_all_physical_paths()
        self.add_changed_files(all_physical_paths)

        # Delete all children before ourselves, so our folder is empty
        for child in self.children:
            child.delete(commit=False)

        physical_path = self.absolute_physical_path
        if self.is_category():
            # Remove our index file first
            index_path = os.path.join(
                physical_path, self.index_file_name)
            os.remove(index_path)
            # Then remove the directory
            os.rmdir(physical_path)
        else:
            os.remove(physical_path)

        if commit:
            # Commit the removal
            self.commit("Deleted '%s'" % (self.wiki_url))

        # Remove ourself from our parent's list
        if self.parent:
            self.parent.remove_child(self)

    def dump(self, indent=0):
        """ For debugging: Print out ourself and our children. """
        logger.debug("%s%s%s (Category: %s, %s, %s)" % (
                     "  " * indent,
                     self.name,
                     self.file_type,
                     self.is_category(),
                     self.wiki_url,
                     self.physical_path))

        for child in self.children:
            child.dump(indent + 1)

    def add_changed_file(self, file):
        if file not in self.changed_files:
            logger.info('Staging file "%s"' % (file))
            self.changed_files.add(file)

    def add_changed_files(self, file_list):
        self.changed_files |= set(file_list)

    def read(self):
        """ Read and return the contents of our physical file. """
        physical_path = self.absolute_physical_path

        if self.is_category():
            physical_path = os.path.join(
                physical_path, self.index_file_name)

        logger.debug("Reading article from '%s'" % physical_path)

        if not os.path.exists(physical_path):
            logger.warning("Could not find article '%s'!" % physical_path)
            return ""

        with GitFile(physical_path) as stream:
            return stream.read().decode('utf-8')

    def write(self):
        """ Write the contents of our physical file. """
        # Move the file before writing to it if its name changed
        if self._file_name != slugify(self._name):
            self.move(name=self._name)

        physical_path = self.absolute_physical_path

        self.add_changed_file(self.physical_path)
        if self.is_category():
            physical_path = os.path.join(
                physical_path, self.index_file_name)
            self.add_changed_file(os.path.join(
                self.physical_path, self.index_file_name))

        with GitFile(physical_path, mode="wb") as stream:
            stream.write(self.text.encode('utf-8'))

        # We wrote the changes, update the wiki's list of unstaged changes
        self.wiki.fetch_unstaged_changes()

        self.modified = False

    def load_history(self):
        """ Load our commit history. """
        self.history = []
        try:
            for entry in self.wiki.git_wiki.get_walker(
                    paths=[self.physical_path.encode('utf-8')]):
                self.history.append(ArticleHistoryEntry(self, entry.commit))
        # A KeyError can occur on freshly created repositories (without commits)
        except KeyError as e:
            pass

    def commit(self, message="", commit_children=False):
        """ Commit changes to the git wiki. Also can commit all of its children recursively. """
        if not message:
            message = "Update article '%s'" % (self.wiki_url)

        logger.info("Commiting '%s' (%s)" %
                    (message, ', '.join(self.changed_files)))
        self.wiki.git_repository.stage(list(self.changed_files))
        self.changed_files = set()

        message = message.encode('utf-8')

        # TODO allow users to change the author's name/mail address
        committer = ("%s <%s>" % (self.wiki.author_name,
                                  self.wiki.author_mail)).encode('utf-8')

        self.wiki.git_repository.do_commit(message,
                                           committer=committer,
                                           author=committer,
                                           commit_timestamp=time.time(), commit_timezone=0,
                                           author_timestamp=time.time(), author_timezone=0)

        # If desired, also commit all of our children
        if commit_children:
            for child in self.children:
                child.commit(commit_children=True)

        self.wiki.fetch_unstaged_changes()
