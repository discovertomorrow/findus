from setuptools import setup, find_packages
from codecs import open
from os import path

from findus import __version__

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='findus',

    version=__version__,

    description='An explorative library for crop field sample data generation via smartphone and open data.',
    long_description=long_description,

    url='https://github.com/discovertomorrow/findus',

    author='Manuel Dörr',
    author_email='manuel.doerr@prognostica.de',

    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: MIT',
        'Programming Language :: Python :: 3.7',
    ],

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=['numpy',
                      'shapely',
                      'geopandas',
                      'rasterio',
                      'matplotlib',
                      'pandas',
                      'sklearn',
                      'requests',
                      'sentinelsat',
                      'skimage',
                      'scipy',
                      'tqdm'],
)
