from setuptools import setup, find_packages

DESCRIPTION = 'Pythonic JavaScript syntax with support for advanced Python functionality'

LONG_DESCRIPTION = """
Rapydscript
===========

RapydScript is a compiler that brings Pythonic syntax to JavaScript,
allowing you to write cleaner JavaScript and even reuse some Python
code in your front-end.

Installation
------------
To install Rapydscript simply use easy_install or pip:

	pip install rapydscript

or

	easy_install rapydscript

Rapydscript requires PyMeta, written by Waldemar Kornewald, which
currently does not have a PyPI package.  It is included as part of the
Rapydscript install.

License
-------
The project is GPLv3, but the output is license free.
See http://www.gnu.org/licenses/gpl-faq.html#WhatCaseIsOutputGPL.

"""

setup(name='rapydscript',
	  version='0.0.2',
	  packages=['rapydscript'],
	  package_data={'rapydscript': ['*.pyj', '*.ometa']},
	  author='Alexander Tsepkov',
	  url='http://rapydscript.pyjeon.com',
	  description=DESCRIPTION,
	  long_description=LONG_DESCRIPTION,
	  platforms=['any'],
	  license='GNU GPL3',
	  install_requires=['pymeta2>=0.0.0'],
	  scripts=['bin/rapydscript'],
	  test_suite = "tests"
)

