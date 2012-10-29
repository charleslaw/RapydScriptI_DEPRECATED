from setuptools import setup, find_packages

DESCRIPTION = 'Pythonic JavaScript syntax with support for advanced Python functionality'

LONG_DESCRIPTION = None
try:
    LONG_DESCRIPTION = open('README.text').read()
except:
    pass

setup(name='rapydscript',
      packages=['rapyd', 'rapyd.pyvascript'],
      package_data={'rapyd': ['*.pyj'], 'rapyd.pyvascript': ['*.ometa']},
      author='Alexander Tsepkov',
      url='http://www.pyjeon.com/projects/rapydscript',
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      platforms=['any'],
      install_requires=[],
      scripts=['rapydscript'],
)
