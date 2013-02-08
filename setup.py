#!/usr/bin/env python

from distutils.core import setup

setup(name='ozite',
      version='0.1',
      description='Tool for image creation and glance upload',
      author='Tomas Karasek',
      author_email='tomas.karasek@cern.ch',
      url='http://www.cern.ch/ai',
      package_dir= {'': 'src'},
      packages=['ozite']
     )
