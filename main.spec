# -*- mode: python -*-

block_cipher = None


a = Analysis(['run.py'],
             pathex=['C:\\Users\\Fabian\\Documents\\Development\\qmdwiki',
	             'C:\\Users\\Fabian\\Documents\\Development\\qmdwiki\\.venv\\Lib\\site-packages'],
             binaries=None,
             datas=[
                #('ui', 'ui'),
                #('styles', 'styles'),
                #('icudt52l.dat', '.')
             ],
             hiddenimports=[
	     	'PyQt5',
	     	'pymdownx',
                'pymdownx.github',
                'pymdownx.magiclink',
                'pymdownx.betterem',
                'pymdownx.tilde',
                'pymdownx.githubemoji',
                'pymdownx.tasklist',
                'pymdownx.headeranchor',
                'pymdownx.superfences',
                'markdown.extensions.tables',
                'markdown.extensions.nl2br'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='mdwiki',
          debug=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='main')
