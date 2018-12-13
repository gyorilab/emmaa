from os import path
from setuptools import setup, find_packages


here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(name='emmaa',
      version='1.0.0',
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
      install_requires=['indra', 'boto3', 'pyyaml']
      )
