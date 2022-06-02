#!/usr/bin/env python3

"""Setuptools based installation module for srecord package

Rob Gaddi, Highland Technology

See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()
package = 'srecord'

# Get the long description from the README file
long_description = (here / "README.rst").read_text(encoding="utf-8")

# Get the version from __init__.py
with (here / package / '__init__.py').open('r') as f:
    for line in f:
        if line.startswith('__version__'):
            _, version, _ = line.split("'")

setup(
    name=package,
    version=version,
    description="Binary image building tools for embedded software",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/NJDFan/python-srecord",
    author="Rob Gaddi",
    author_email="rgaddi@highlandtechnology.com",
      
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Embedded Systems",
    ],
    keywords="srecord, binary, eeprom, flash",
    packages=[package],
    python_requires=">=3.6"
)
