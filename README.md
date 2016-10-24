# Splatalogue Update Scripts
###### Author: Nathan A. Seifert

This package contains a number of tools used to update portions of the Splatalogue database. Although a number of
tools are featured here, the main script -- run.py -- features a GUI with helper menus for a small set of common tasks.

### Installation

**THIS PACKAGE REQUIRES LINUX. DOES NOT WORK ON WINDOWS SINCE MYSQL INTERFACING IS WORTHLESS IN WINDOWS **

These tools require, at minimum, **Python 2.7.x with pip installed**. If you're on Python 2.7.9 or greater, then you're in
luck -- pip is already included! If pip is not installed in your python distribution, you can find download instructions [at this link](https://pip.pypa.io/en/latest/installing/)

If you need a nice Python distribution that has a majority of the required libraries installed already, I recommend the Anaconda
distribution, which can be found [here](https://www.continuum.io/downloads)


1. Install MySQL client/server libraries
    1. If you're using Debian/Ubuntu, it's super easy: `sudo apt-get install mysql-server libmysqlclient-dev`
    2. in Fedora, I think this should work: `yum install mysql mysql-server`
2. Install prerequisite libraries
   1. The easy way: use pip to install the prerequisites using the following command in the main
   splatalogue directory: `pip install -r requirements.txt`
   2. The hard way: This package requires the following third-party libraries:
     - Pandas 0.18.0
     - Numpy (anything recent should be fine)
     - MySQL-python (anything recent should be fine)
     - [Easygui 0.98.0](https://github.com/robertlugg/easygui/) (also available in pip)
     - BeautifulSoup 4


### Use

To run, in the terminal type `python run.py`. In order to connect to the SQL database, you can either enter the
information manually or use an input file. An example input file for SQL connections can be found in the sample_inputs/
directory. If you don't want to input your password as plaintext, you can remove the `pass` entry in the input file or,
if entering the access information manually via the GUI, leave the password box empty. The GUI will then ask you to
enter your password, which is not handled in plain-text.

For JPL and CDMS additions, nothing else is required.

For custom entries, e.g. into the SLAIM sub-database, you will need an input file for the metadata entry. A working sample
metadata input file can be found in the sample_inputs/ directory. The rest of the required information is filled out
in the GUI.