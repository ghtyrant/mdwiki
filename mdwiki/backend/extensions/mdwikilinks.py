'''
WikiLinks Extension for Python-Markdown
======================================

Converts [[WikiLinks]] to relative links.

See <https://Python-Markdown.github.io/extensions/wikilinks>
for documentation.

Original code Copyright [Waylan Limberg](http://achinghead.com/).

All changes Copyright The Python Markdown Project

License: [BSD](http://www.opensource.org/licenses/bsd-license.php)

'''

from markdown.extensions import Extension
from markdown.inlinepatterns import Pattern
from markdown.util import etree


def build_url(label, base, end):
    """ Build a url from the label, a base, and an end. """
    clean_label = label.replace(':', '/')
    return '%s%s%s' % (base, clean_label, end)


def build_label(label):
    return label.split(':')[-1]


def url_exists(url):
    print("ORIGINAL URL")
    return True


class WikiLinkExtension(Extension):

    def __init__(self, *args, **kwargs):
        self.config = {
            'base_url': ['/', 'String to append to beginning or URL.'],
            'end_url': ['/', 'String to append to end of URL.'],
            'html_class': ['wikilink', 'CSS hook. Leave blank for none.'],
            'build_url': [build_url, 'Callable that formats URL from label.'],
            'build_label': [build_label, 'Callable that formats the label.'],
            'url_exists': [url_exists,
                           'Callable that returns wether a URL exists']
        }

        super(WikiLinkExtension, self).__init__(*args, **kwargs)

    def extendMarkdown(self, md, md_globals):
        self.md = md

        # append to end of inline patterns
        WIKILINK_RE = r'\[\[([\w0-9_: -]+)\]\]'
        wikilinkPattern = WikiLinks(WIKILINK_RE, self.getConfigs())
        wikilinkPattern.md = md
        md.inlinePatterns.add('wikilink', wikilinkPattern, "<not_strong")


class WikiLinks(Pattern):
    def __init__(self, pattern, config):
        super(WikiLinks, self).__init__(pattern)
        self.config = config

    def handleMatch(self, m):
        if m.group(2).strip():
            a = etree.Element('a')
            base_url, end_url, html_class = self._getMeta()
            label = m.group(2).strip()
            a.set('title', label)
            url = self.config['build_url'](label, base_url, end_url)
            label_short = self.config['build_label'](label)
            a.set('href', url)

            if not self.config['url_exists'](url):
                a.set('class', 'missing')
                a.text = label
            else:
                a.text = label_short
        else:
            a = ''
        return a

    def _getMeta(self):
        """ Return meta data or config data. """
        base_url = self.config['base_url']
        end_url = self.config['end_url']
        html_class = self.config['html_class']
        if hasattr(self.md, 'Meta'):
            if 'wiki_base_url' in self.md.Meta:
                base_url = self.md.Meta['wiki_base_url'][0]
            if 'wiki_end_url' in self.md.Meta:
                end_url = self.md.Meta['wiki_end_url'][0]
            if 'wiki_html_class' in self.md.Meta:
                html_class = self.md.Meta['wiki_html_class'][0]
        return base_url, end_url, html_class
