import os
import shutil
import time
import logging
import re

from dulwich.file import GitFile

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
        git_repos = self.article.get_wiki().get_git()

        object_store = git_repos.object_store
        old_tree = self.commit.tree

        new_tree = git_repos[git_repos.head()].tree

        old_lines = []
        changes = object_store.tree_changes(old_tree, new_tree)
        for (oldpath, newpath), (_, _), (oldsha, _) in changes:
            if not newpath or not oldpath:
                continue

            if (newpath.decode('utf-8') == self.article.get_physical_path()
                    and oldpath.decode('utf-8') == self.article.get_physical_path()):

                if oldsha:
                    old_object = object_store[oldsha]
                    old_lines = old_object.as_raw_string().decode('utf-8').splitlines(keepends=True)

                    break

        if old_lines and not old_lines[-1].endswith('\n'):
            old_lines[-1] += '\n'

        return old_lines


class Article:
    def __init__(self, name, file_type, parent, wiki, is_directory=False):
        self.name = name
        self.file_type = file_type
        self.parent = parent
        self.wiki = wiki
        self.is_directory = is_directory

        self.children = []
        self.history = []
        self.links = []

        self.text = ""
        self.modified = False

        self.changed_files = set()

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Article '%s'>" % self.name

    @classmethod
    def new_from_file_name(cls, file_name, parent, wiki):
        name, file_type = os.path.splitext(file_name)
        return cls.new(name, file_type, parent, wiki)

    @classmethod
    def new(cls, name, file_type, parent, wiki):
        return Article(name, file_type, parent, wiki)

    def is_root(self):
        return self.parent is None

    def set_wiki(self, wiki):
        self.wiki = wiki

    def get_wiki(self):
        return self.wiki

    def is_category(self):
        return self.is_directory

    def get_parent(self):
        return self.parent

    def set_text(self, text):
        if text != self.text:
            self.modified = True
            self.refresh_links()

        self.text = text

    def get_text(self):
        if not self.text:
            self.text = self.read()
        return self.text

    def set_name(self, name):
        self.name = name

    def get_name(self):
        return self.name

    def get_file_name(self):
        if self.is_category():
            return self.name

        return self.name + self.file_type

    def set_file_type(self, file_type):
        if file_type == self.file_type:
            return

        old_physical_path = self.get_physical_path()

        if self.is_category():
            old_physical_path = self.get_index_file_name(old_physical_path)

        self.add_changed_file(old_physical_path)
        self.file_type = file_type

        new_physical_path = self.get_physical_path()

        if self.is_category():
            new_physical_path = self.get_index_file_name(old_physical_path)

        os.rename(os.path.join(self.get_wiki().get_physical_path(), old_physical_path),
                  os.path.join(self.get_wiki().get_physical_path(), new_physical_path))
        self.add_changed_file(new_physical_path)
        self.commit("Changed file type of '%s' to '%s'" %
                    (self.get_wiki_url(), self.get_file_type()))

    def get_file_type(self):
        return self.file_type

    def append_file_extension(self, name):
        return name + self.file_type

    def get_index_file_name(self):
        if self.is_category():
            return INDEX_FILE_NAME + self.file_type

        return ""

    def export(self, output_path, renderers):
        target_path = os.path.join(output_path, self.get_physical_path())

        if self.is_directory:
            target_path = os.path.join(target_path, 'index.html')
        else:
            target_path = os.path.splitext(target_path)[0] + '.html'

        target_dir = os.path.dirname(target_path)

        if self.wiki.get_root() != self:

            if not os.path.exists(target_dir):
                os.makedirs(target_dir)

            with open(target_path, 'wb') as stream:
                renderer = renderers[self.get_file_type()]
                stream.write(renderer.render(self.get_text()).encode('utf-8'))

        for child in self.children:
            child.export(target_dir, renderers)

    def refresh_links(self):
        links = re.findall(r'\[\[([^\[\]|]*)[^\[\]]*\]\]', self.get_text())

        self.links = []
        for link in links:
            article = self.get_wiki().get_article_by_url(link.replace(':', '/'))

            if article:
                self.links.append(article)

    def get_wiki_url(self):
        """ This returns the URL of this article, relative to the root of the wiki.
        e.g. 'test/article'
        """
        if not self.is_root():
            return os.path.join(self.get_parent().get_wiki_url(), self.get_name())
        else:
            return self.get_name()

    def get_absolute_physical_path(self):
        """ This returns the absolute, physical path to either the file or the folder of this article. """
        return os.path.join(self.get_wiki().get_physical_path(), self.get_physical_path())

    def get_physical_path(self):
        """ This returns the relative, physical path to either the file or the folder of this article. """
        if not self.is_root():
            return os.path.join(self.get_parent().get_physical_path(), self.get_file_name())
        else:
            return ""  # self.get_file_name()

    def add_child(self, article):
        """ This adds a child to this article, turning it into a category if it isn't one already. """
        # This is the first child, convert to category!
        if not (self.has_children() or self.is_category()):
            self.convert_to_folder()

        self.children.append(article)

    def remove_child(self, article):
        self.children.remove(article)

        if not self.has_children() and self.is_category():
            self.convert_to_file()

    def get_child_by_name(self, name):
        for child in self.children:
            if child.get_name().lower() == name.lower():
                return child

        return None

    def get_all_physical_paths(self):
        files = []

        if self.is_category():
            files.append(os.path.join(self.get_physical_path(),
                                      self.get_index_file_name()))
        else:
            files.append(self.get_physical_path())

        for child in self.children:
            files += child.get_all_physical_paths()

        return files

    def has_children(self):
        return len(self.children) > 0

    def move(self, name, parent=None):
        if parent is None:
            parent = self.get_parent()

        # Nothing changed? Nothing to do then!
        if name == self.get_name() and parent == self.get_parent():
            return

        # Store current paths for later use
        old_wiki_url = self.get_wiki_url()
        old_physical_path = self.get_physical_path()
        old_absolute_physical_path = self.get_absolute_physical_path()

        if parent != self.get_parent():
            self.add_changed_files(self.get_all_physical_paths())

        # Change our name
        self.name = name

        # If this is simply a rename, add the old and the new name to the commit
        if parent == self.get_parent():
            self.add_changed_file(old_physical_path)
            self.add_changed_file(self.get_physical_path())

        if parent != self.get_parent():
            # If the new parent isn't a folder yet, convert it
            if not parent.is_category():
                parent.convert_to_folder()

        new_path = os.path.join(
            parent.get_absolute_physical_path(), self.get_file_name())

        # This will move & rename this article
        shutil.move(old_absolute_physical_path, new_path)

        if parent != self.get_parent():
            # Remove ourself from the old parent
            self.get_parent().remove_child(self)

            # ... and add us to the new one
            self.parent = parent
            self.get_parent().add_child(self)

            self.add_changed_files(self.get_all_physical_paths())

        self.commit(message="Moved '%s' to '%s'." %
                    (old_wiki_url, self.get_wiki_url()))

    def convert_to_folder(self):
        """This function turns an article file into a folder, keeping its content.
        e.g. from 'test.md' to 'test' (directory) and '/test/_index.md' (file)
        """
        # This points to '/test.md'
        physical_path = self.get_absolute_physical_path()

        self.add_changed_file(self.get_physical_path())

        # Remove the file extension to get the path to the new folder
        new_folder_path = os.path.splitext(physical_path)[0]

        # Create the folder
        os.mkdir(new_folder_path, DEFAULT_FOLDER_PERMISSION)

        # Move and rename the old file (e.g. from '/test.md' to '/test/_index.md')
        self.is_directory = True
        new_index_file = os.path.join(
            new_folder_path, self.get_index_file_name())
        os.rename(physical_path, new_index_file)

        # The new file_name will the name of the folder, so simply remove the file extension
        self.add_changed_file(os.path.join(
            self.get_physical_path(), self.get_index_file_name()))

        # Commit the new file and the old one, so git knows we have moved it
        self.commit("Turned '%s' into a category." % (self.get_wiki_url()))

    def convert_to_file(self):
        """This function does the opposite of convert_to_folder().
        e.g. from 'test/_index.md' (folder + file) to 'test.md'
        """
        # This points to '/test'
        physical_path = self.get_absolute_physical_path()

        # This points to '/test/_index.md'
        index_file_path = os.path.join(
            physical_path, self.get_index_file_name())
        self.add_changed_file(os.path.join(
            self.get_physical_path(), self.get_index_file_name()))

        # Add the file extension to get the new file name ('/test' becomes '/test.md')
        new_file_path = self.append_file_extension(physical_path)

        # Move and rename the index file
        os.rename(index_file_path, new_file_path)

        # Remove the old directory - this should be guaranteed to be empty, because
        # we only get called when this article has no more children
        # TODO Catch the error in case it is NOT empty and handle it gracefully
        os.rmdir(physical_path)

        # Store the old index file path before we change our file_name
        old_index_path = os.path.join(
            self.get_physical_path(), self.get_index_file_name())

        # Simply add the file extension to the current file name

        # Commit the new file and the old index file, so git knows we have moved it
        self.add_changed_file(self.get_physical_path())
        self.commit("Turned '%s' into an article." %
                    (self.get_wiki_url()), [old_index_path])

    def has_unstaged_changes(self):
        """ Return wether this article has changes that haven't been committed yet. """
        physical_path = self.get_physical_path()

        if self.is_category():
            physical_path = os.path.join(
                physical_path, self.get_index_file_name())

        return self.get_wiki().is_path_unstaged(physical_path)

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

    def create_article_by_path(self, path):
        name, file_type = os.path.splitext(path)

        if not file_type:
            absolute_physical_path = os.path.join(
                self.wiki.get_physical_path(), path)
            for filename in os.listdir(absolute_physical_path):
                if filename.startswith(INDEX_FILE_NAME):
                    file_type = os.path.splitext(filename)[1]
                    break

        self.create_article_by_url(name, file_type)

    def create_article_by_url(self, url, file_type):
        """ Create an article and all categories in between. Works similar to resolve(). """

        # For convenience, the user can call this function with a string (e.g. '/test/category/article')
        # We will turn it into a list for him (e.g. ['test', 'category', 'article'])
        if isinstance(url, str):
            url = split_path(url)

        name = url.pop(0)
        article = self.get_child_by_name(name)

        if article is None:
            article = Article(name,
                              file_type,
                              self,
                              self.get_wiki(),
                              len(url) > 0)

            self.add_child(article)

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

        physical_path = self.get_absolute_physical_path()
        if self.is_category():
            # Remove our index file first
            index_path = os.path.join(
                physical_path, self.get_index_file_name())
            os.remove(index_path)
            # Then remove the directory
            os.rmdir(physical_path)
        else:
            os.remove(physical_path)

        if commit:
            # Commit the removal
            self.commit("Deleted '%s'" % (self.get_wiki_url()))

        # Remove ourself from our parent's list
        if self.get_parent():
            self.get_parent().remove_child(self)

    def dump(self, indent=0):
        """ For debugging: Print out ourself and our children. """
        print("%s%s%s (Category: %s, %s, %s)" % (
              "  " * indent,
              self.name,
              self.file_type,
              self.is_category(),
              self.get_wiki_url(),
              self.get_physical_path()))

        for child in self.children:
            child.dump(indent + 1)

    def add_changed_file(self, file):
        if file not in self.changed_files:
            self.changed_files.add(file)

    def add_changed_files(self, file_list):
        self.changed_files |= set(file_list)

    def read(self):
        """ Read and return the contents of our physical file. """
        physical_path = self.get_absolute_physical_path()

        if self.is_category():
            physical_path = os.path.join(
                physical_path, self.get_index_file_name())

        logger.debug("Reading article from '%s'" % physical_path)

        if not os.path.exists(physical_path):
            return ""

        with GitFile(physical_path) as stream:
            return stream.read().decode('utf-8')

    def write(self):
        """ Write the contents of our physical file. """
        physical_path = self.get_absolute_physical_path()

        self.add_changed_file(self.get_physical_path())
        if self.is_category():
            physical_path = os.path.join(
                physical_path, self.get_index_file_name())
            self.add_changed_file(os.path.join(
                self.get_physical_path(), self.get_index_file_name()))

        with GitFile(physical_path, mode="wb") as stream:
            stream.write(self.text.encode('utf-8'))

        # We wrote the changes, update the wiki's list of unstaged changes
        self.get_wiki().fetch_unstaged_changes()

        self.modified = False

    def load_history(self):
        """ Load our commit history. """
        self.history = []
        try:
            for entry in self.wiki.git_wiki.get_walker(
                    paths=[self.get_physical_path().encode('utf-8')]):
                self.history.append(ArticleHistoryEntry(self, entry.commit))
        # A KeyError can occur on freshly created repositories (without commits)
        except KeyError as e:
            pass

    def commit(self, message="", commit_children=False):
        """ Commit changes to the git wiki. Also can commit all of its children recursively. """
        if not message:
            message = "Update article '%s'" % (self.get_wiki_url())

        print("Commiting '%s' (%s)" % (message, ', '.join(self.changed_files)))
        self.get_wiki().get_git().stage(list(self.changed_files))
        self.changed_files = set()

        message = message.encode('utf-8')

        # TODO allow users to change the author's name/mail address
        committer = ("%s <%s>" % (self.get_wiki().get_author_name(),
                                  self.get_wiki().get_author_mail())).encode('utf-8')

        self.get_wiki().get_git().do_commit(message,
                                            committer=committer,
                                            author=committer,
                                            commit_timestamp=time.time(), commit_timezone=0,
                                            author_timestamp=time.time(), author_timezone=0)

        # If desired, also commit all of our children
        if commit_children:
            for child in self.children:
                child.commit(commit_children=True)

        self.get_wiki().fetch_unstaged_changes()
