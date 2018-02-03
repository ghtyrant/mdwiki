import logging
import os

import pytest

from ..backend.wiki import Wiki

logging.basicConfig(level=logging.DEBUG)


def get_full_path(wiki, article):
    return os.path.join


@pytest.fixture
def wiki(tmpdir):
    return Wiki.create('TempWiki', str(tmpdir), '', '.md', 'Test Author', 'test@author.com', '')


def test_create_simple(wiki):
    article_one = wiki.create_article('ArticleOne', '.md', wiki.get_root())

    # Verify that the file really exists
    assert os.path.isfile(article_one.get_absolute_physical_path()) is True

    # And verify that is has been added to the index
    indexed_files = sorted([x.decode('utf-8')
                            for x in wiki.git_repository.open_index()])
    assert indexed_files == sorted(
        ['.wikiconfig', '_index.md', article_one.get_file_name()])


def test_delete_simple(wiki):
    article_one = wiki.create_article('ArticleOne', '.md', wiki.get_root())

    article_one.delete()

    # Verify that the file really exists
    assert os.path.isfile(article_one.get_absolute_physical_path()) is False

    # And verify that is has been added to the index
    indexed_files = sorted([x.decode('utf-8')
                            for x in wiki.git_repository.open_index()])
    assert indexed_files == sorted(['.wikiconfig', '_index.md'])


def test_create_category(wiki):
    article_one = wiki.create_article('ArticleOne', '.md', wiki.get_root())
    article_two = wiki.create_article('ArticleTwo', '.md', article_one)

    # Verify that the file really exists
    assert os.path.isdir(article_one.get_absolute_physical_path()) is True
    assert os.path.isfile(article_two.get_absolute_physical_path()) is True

    # And verify that is has been added to the index
    indexed_files = sorted([x.decode('utf-8')
                            for x in wiki.git_repository.open_index()])
    assert indexed_files == sorted(['.wikiconfig',
                                    '_index.md',
                                    article_two.get_physical_path().replace('\\', '/'),
                                    os.path.join(article_one.get_physical_path(
                                    ), article_one.get_index_file_name()).replace('\\', '/')
                                    ])


def test_destroy_category(wiki):
    article_one = wiki.create_article('ArticleOne', '.md', wiki.get_root())
    article_two = wiki.create_article('ArticleTwo', '.md', article_one)

    article_two.delete()

    print(article_one.get_absolute_physical_path())

    # Verify that the file really exists
    assert os.path.isfile(article_one.get_absolute_physical_path()) is True

    # And verify that is has been added to the index
    indexed_files = sorted([x.decode('utf-8')
                            for x in wiki.git_repository.open_index()])
    assert indexed_files == sorted(
        ['.wikiconfig', '_index.md', article_one.get_file_name()])


def test_rename_article(wiki):
    article_one = wiki.create_article('ArticleOne', '.md', wiki.get_root())
    old_path = article_one.get_absolute_physical_path()
    old_file_name = article_one.get_file_name()
    article_one.move('ArticleTwo')

    # Verify that the filename has changed
    assert old_file_name != article_one.get_file_name()

    # Verify that the file really exists
    assert os.path.isfile(old_path) is False
    assert os.path.isfile(article_one.get_absolute_physical_path()) is True

    # And verify that is has been added to the index
    indexed_files = sorted([x.decode('utf-8')
                            for x in wiki.git_repository.open_index()])
    assert indexed_files == sorted(
        ['.wikiconfig', '_index.md', article_one.get_file_name()])


def test_move_article(wiki):
    article_one = wiki.create_article('ArticleOne', '.md', wiki.get_root())
    article_two = wiki.create_article('ArticleTwo', '.md', wiki.get_root())
    old_path = article_one.get_absolute_physical_path()

    with pytest.raises(ValueError):
        article_one.move(parent=article_one)

    article_one.move(parent=article_two)

    # Verify that the file really exists
    assert os.path.exists(old_path) is False
    assert os.path.isfile(article_one.get_absolute_physical_path()) is True
    assert os.path.isdir(article_two.get_absolute_physical_path()) is True

    # And verify that is has been added to the index
    indexed_files = sorted([x.decode('utf-8')
                            for x in wiki.git_repository.open_index()])
    assert indexed_files == sorted(['.wikiconfig',
                                    '_index.md',
                                    os.path.join(article_two.get_physical_path(
                                    ), article_two.get_index_file_name()).replace('\\', '/'),
                                    article_one.get_physical_path().replace('\\', '/')
                                    ])


def test_move_category(wiki):
    article_one = wiki.create_article('ArticleOne', '.md', wiki.get_root())
    article_two = wiki.create_article('ArticleTwo', '.md', article_one)
    article_three = wiki.create_article('ArticleThree', '.md', wiki.get_root())
    old_path = article_three.get_absolute_physical_path()

    article_one.move(parent=article_three)

    # Verify that the file really exists
    assert os.path.exists(old_path) is False
    assert os.path.isdir(article_one.get_absolute_physical_path()) is True
    assert os.path.isfile(article_two.get_absolute_physical_path()) is True
    assert os.path.isdir(article_three.get_absolute_physical_path()) is True

    # And verify that is has been added to the index
    indexed_files = sorted([x.decode('utf-8')
                            for x in wiki.git_repository.open_index()])
    assert indexed_files == sorted(['.wikiconfig',
                                    '_index.md',
                                    os.path.join(article_three.get_physical_path(
                                    ), article_three.get_index_file_name()).replace('\\', '/'),
                                    os.path.join(article_one.get_physical_path(
                                    ), article_one.get_index_file_name()).replace('\\', '/'),
                                    article_two.get_physical_path().replace('\\', '/')
                                    ])
