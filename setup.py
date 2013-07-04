# -*- coding: utf8 -*-
from distutils.core import setup

setup(name='ncts',
    version='0.1a',
    description='Frontend for Task Spooler',
    author='Tomáš Ehrlich',
    author_email='tomas.ehrlich@gmail.com',
    url='https://github.com/elvard/ncts',
    download_url='https://github.com/elvard/ncts/archive/master.zip',
    packages=['ncts'],
    scripts=['bin/ncts'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console :: Curses',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Topic :: System :: Monitoring',
    ]
)
