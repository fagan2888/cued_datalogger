from setuptools import setup
import sys
import subprocess
from os.path import isfile

try:
    from unittest.mock import MagicMock
except:
    from mock import Mock as MagicMock

class Mock(MagicMock):
    @classmethod
    def __getattr__(cls, name):
            return MagicMock()

MOCK_MODULES = ['pyaudio']
sys.modules.update((mod_name, Mock()) for mod_name in MOCK_MODULES)


def version():
    """Get version number"""
    with open('datalogger/VERSION') as f:
        return f.read()

def readme():
    """Get text from the README.rst"""
    with open('README.rst') as f:
        return f.read()

setup(name='cued-datalogger',
      version=version(),
      description='The CUED DataLogger for acquiring and analysing data',
      long_description=readme(),
      url='https://bitbucket.org/tab53/cued_datalogger/',
      author='Theo Brown, En Yi Tee',
      author_email='tab53@cam.ac.uk, eyt21@cam.ac.uk',
      license='BSD 3-Clause License',
      packages=['datalogger',
                'datalogger/acquisition',
                'datalogger/analysis',
                'datalogger/api'],
      # TODO
      # If you include this in the setup code, when it tries to install
      # itself in an Anaconda environment, a lot of things break. Fix this.
      # (currently the workaround is telling the user to install some stuff)
      install_requires=[
                      'PyQt5>=5.9',
                      'numpy>=1.11.3',
                      'scipy>=0.18.1',
                      'pyqtgraph>=0.9.10',
                      'matplotlib>=1.5.1',
                      'PyDAQmx>=1.3.2'],
                      #'pyaudio>=0.2.11'],
      zip_safe=True,
      include_package_data=True)
