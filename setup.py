import re
from os import path
from setuptools import setup, find_packages


here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


with open(path.join(here, 'emmaa', '__init__.py'), 'r') as fh:
    for line in fh.readlines():
        match = re.match(r'__version__ = \'(.+)\'', line)
        if match:
            emmaa_version = match.groups()[0]
            break
    else:
        raise ValueError('Could not get version from emmaa/__init__.py')


setup(name='emmaa',
      version=emmaa_version,
      description='Ecosystem of Machine-maintained Models with ' + \
                  'Automated Analysis',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/indralab/emmaa',
      author='EMMAA developers, Harvard Medical School',
      author_email='benjamin_gyori@hms.harvard.edu',
      classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
        ],
      packages=find_packages(),
      install_requires=['indra', 'boto3', 'jsonpickle', 'kappy==4.0.94',
                        'pygraphviz', 'fnvhash', 'sqlalchemy', 'inflection',
                        'pybel==0.15', 'flask_jwt_extended==3.25.0', 'gilda',
                        'tweepy'],
      extras_require={'test': ['nose', 'coverage', 'moto[iam]',
                               'sqlalchemy_utils']}
      )
