from .article import Article
from .constants import INDEX_FILE_NAME, CONFIG_FILE_NAME, FALLBACK_RENDERER
from .util import natural_sort_key

import os
import configparser
import logging

from dulwich.repo import Repo as DulwichWiki
from dulwich.index import get_unstaged_changes
from dulwich.objectspec import parse_reftuples
from dulwich.client import get_transport_and_path_from_url
from dulwich.errors import SendPackError, UpdateRefsError
from dulwich.protocol import ZERO_SHA
import dulwich.client
from dulwich.contrib.paramiko_vendor import ParamikoSSHVendor
dulwich.client.get_ssh_vendor = ParamikoSSHVendor

logger = logging.getLogger(__name__)


class Wiki:
    def __init__(self, path, dulwich_repos=None):
        self._name = ""
        self._default_file_type = ".md"
        self._author_name = ""
        self._author_mail = ""
        self._remote_url = ""

        self._path = path
        self.config_path = os.path.join(path, CONFIG_FILE_NAME)
        self.git_repository = dulwich_repos or DulwichWiki(path)
        self.unstaged_changes = []

        self.read_config()
        self.root = Article(
            self._name, self._default_file_type, None, self, True)

        git_config = self.git_repository.get_config()

        try:
            self.remote_url = git_config.get(
                (b"remote", b"origin"), b"url").decode('utf-8')
            self.remote_fetch_refs = git_config.get(
                (b"remote", b"origin"), b"fetch")
        except KeyError:
            self.remote_fetch_refs = b"+refs/heads/master:refs/remotes/origin/master"

        # Dulwich does not support * in refs yet, replace it with master
        if b'*' in self.remote_fetch_refs:
            self.remote_fetch_refs = self.remote_fetch_refs.replace(
                b'*', b'master')

        # Fetch unstaged changes before importing index so that articles
        # will have the correct icon already
        self.fetch_unstaged_changes()
        self.import_current_index()

        self.root.dump()

    @classmethod
    def open(cls, path):
        """ Open a repository folder and return a new instance of Wiki. """
        # There has to be a .git directory for us to open this repository
        if not os.path.exists(os.path.join(path, ".git")):
            return None

        return Wiki(path)

    @classmethod
    def create(cls, name, path, remote_url, file_type, author_name, author_mail, template_text):
        git_repos = DulwichWiki.init(path)
        wiki = Wiki(path, git_repos)

        wiki.update_config(name, remote_url, file_type,
                           author_name, author_mail)

        # Initialize index page with template
        wiki.root.text = template_text

        return wiki

    @property
    def physical_path(self):
        return self._path

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name
        self.root.name = name
        self.write_config()

    @property
    def default_file_type(self):
        return self._default_file_type

    @default_file_type.setter
    def default_file_type(self, file_type):
        self._default_file_type = file_type
        self.write_config()

    @property
    def author_name(self):
        return self._author_name

    @author_name.setter
    def author_name(self, name):
        self._author_name = name
        self.write_config()

    @property
    def author_mail(self):
        return self._author_mail

    @author_mail.setter
    def author_mail(self, mail):
        self._author_mail = mail
        self.write_config()

    @property
    def remote_url(self):
        return self._remote_url

    @remote_url.setter
    def remote_url(self, remote_url):
        self._remote_url = remote_url

        config = self.git_repository.get_config()
        config.set((b"remote", b"origin"), b"url", remote_url.encode('utf-8'))
        config.set((b"remote", b"origin"), b"fetch",
                   b"+refs/heads/*:refs/remotes/origin/*")

        # Set up local master to track remote branch
        config.set((b"branch", b"master"), b"remote", b"origin")
        config.set((b"branch", b"master"), b"merge", b"refs/heads/master")
        config.write_to_path()

    def update_config(self, name, remote_url, file_type, author_name, author_mail):
        self._default_file_type = file_type
        self._author_name = author_name
        self._author_mail = author_mail
        self._name = name

        self.remote_url = remote_url

        self.write_config()

    def read_config(self):
        if not os.path.exists(self.config_path):
            return

        config = configparser.ConfigParser()
        config.read(self.config_path)

        try:
            repos_config = config['repos']
            self._name = repos_config.get('name')
            self._default_file_type = repos_config.get(
                'default_file_type', fallback=FALLBACK_RENDERER)
            self._author_name = repos_config.get(
                'author', fallback="Anonymous")
            self._author_mail = repos_config.get('mail', fallback="<>")
        except KeyError as e:
            logger.exception(
                "Error reading wiki config '%s': Missing '%s'." % (self.config_path, e))

    def write_config(self):
        config = configparser.ConfigParser()
        config["repos"] = {
            "name": self.name,
            "default_file_type": self.default_file_type,
            "author": self.author_name,
            "mail": self.author_mail,
        }

        with open(self.config_path, "w") as stream:
            config.write(stream)

        self.root.add_changed_file(CONFIG_FILE_NAME)
        self.root.commit(message="Update wiki configuration.")

    def import_current_index(self):
        """ Imports the current index of the git repository and creates Article instances for every file. """
        indexed_files = sorted(
            list(self.git_repository.open_index()), key=natural_sort_key)

        for file_name in indexed_files:
            file_name = file_name.decode("utf-8")

            # Ignore files starting with '.' or '_' (e.g. '.gitignore', '_index.md')
            basename = os.path.basename(file_name)
            if basename.startswith(".") or basename.startswith(INDEX_FILE_NAME):
                continue

            self.root.create_article_by_path(file_name)

    def fetch_unstaged_changes(self):
        """ Fetch the current list of unstaged changes from git. """
        self.unstaged_changes = []
        try:
            for change in get_unstaged_changes(self.git_repository.open_index(), self.physical_path):
                self.unstaged_changes.append(change.decode('utf-8'))
        except FileNotFoundError:
            pass

    def is_path_unstaged(self, article_path):
        # XXX Dulwich returns Unix style paths (with forward slashes), even on Windows
        # As a hotfix, we convert article_path to use forward slashes
        tmp_path = article_path.replace("\\", "/")
        return tmp_path in self.unstaged_changes

    def has_unstaged_changes(self):
        return len(self.unstaged_changes) > 0

    def create_article(self, name, file_type, parent):
        article = Article(name, file_type, parent, self)

        return article

    def close(self):
        self.git_repository.close()

    def pull(self, progress_func, username=None, password=None):
        """ This pulls updates from a remote repository.
        This code has been take from dulwich.porcelain.
        """
        if not self.remote_url:
            return

        selected_refs = []

        def determine_wants(remote_refs):
            selected_refs.extend(parse_reftuples(remote_refs,
                                                 self.git_repository.refs, self.remote_fetch_refs))
            return [remote_refs[lh] for (lh, rh, force) in selected_refs]

        logger.info("Pulling from '%s' ..." % (self.remote_url))
        client, path = get_transport_and_path_from_url(self.remote_url)

        if password:
            client.ssh_vendor.ssh_kwargs["password"] = password

        try:
            remote_refs = client.fetch(path.encode('utf-8'), self.git_repository, progress=progress_func,
                                       determine_wants=determine_wants)
        except FileExistsError:
            logger.exception("Pack already exists. Possibly a bug in dulwich.")
            return

        for (lh, rh, force) in selected_refs:
            self.git_repository.refs[rh] = remote_refs[lh]

        self.git_repository.reset_index()

    def push(self, progress_func, username=None, password=None):
        """ This pushes updates to a remote repository.
        This code has been take from dulwich.porcelain.
        """
        if not self.remote_url:
            return

        logger.info("Pushing to '%s' ..." % (self.remote_url))

        # Get the client and path
        client, path = get_transport_and_path_from_url(self.remote_url)

        if password:
            client.ssh_vendor.ssh_kwargs["password"] = password

        selected_refs = []
        refspecs = b"+refs/heads/master"

        def update_refs(refs):
            selected_refs.extend(parse_reftuples(
                self.git_repository.refs, refs, refspecs))
            new_refs = {}
            # TODO: Handle selected_refs == {None: None}
            for (lh, rh, force) in selected_refs:
                if lh is None:
                    new_refs[rh] = ZERO_SHA
                else:
                    new_refs[rh] = self.git_repository.refs[lh]
            return new_refs

        try:
            client.send_pack(path.encode('utf-8'), update_refs,
                             self.git_repository.object_store.generate_pack_contents, progress=progress_func)
            progress_func(b"Push successful.\n")
        except (UpdateRefsError, SendPackError) as e:
            progress_func(b"Push failed -> " +
                          e.message.encode('utf8') + b"\n")

    #####################################################################
    # Convenience functions, will be passed through to the root article #
    #####################################################################
    def get_article_by_url(self, url):
        return self.root.resolve(url)

    def commit_all(self):
        self.root.commit(commit_children=True)

    def create_article_by_url(self, url, file_type):
        return self.root.create_article_by_url(url, file_type)
