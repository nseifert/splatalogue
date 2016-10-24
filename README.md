# Splatalogue Update Scripts
###### Author: Nathan A. Seifert

This package contains a number of tools used to update portions of the Splatalogue database. Although a number of
tools are featured here, the main script -- run.py -- features a GUI with helper menus for a small set of common tasks.

### Installation

*THIS PACKAGE REQUIRES LINUX. DOES NOT WORK ON WINDOWS SINCE MYSQL INTERFACING IS WORTHLESS IN WINDOWS.*

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
     - [Easygui 0.98.0](https://github.com/robertlugg/easygui/) (also available in pip and in this package)
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


### Quantum number formatting tips

At the moment, adding new quantum number formatting for CAT-file based submissions (e.g. JPL, CDMS) must be done manually
in the `scrapers/QNFormat.py` file.

Additional quantum number formatting schemes can be added to `fmt_dict` inside the `format_it()` function inside QNFormat.
`fmt_dict` is a dictionary with key values associated with the "quantum number tag" integer found in a CAT file. Each value
associated with these keys is a tuple/list with dictionaries, each corresponding to a different type of style for that specific
QN tag key. For instance, consider the values for QN tag 203:

`203: ({'fmt':'{:d}({:d}) - {:d}({:d}), F = {:d} - {:d}',
        'series': [0, 1, 3, 4, 2, 5], 'tag': 'Symmetric top with 1 hyperfine nuclei.'},
       {'fmt': '', 'series':[0], 'tag': 'Symmetric top with parity and weird electronic spin QN Omega (custom)'},
       ),`

In this example, 203 has two possible style options. Each style has three required keys: `'fmt'`, `'series'`, and `'tag'`.

Consider the first entry in the tuple contained within key 203.

**fmt** specifies the string formatting for the quantum numbers -- in this case 203 implies a symmetric top with hyperfine
splitting, so the fmt is `Jup(Kup) - Jdown(Kdown), F = Fup - Fdown`, where each label has been replaced with a `{:d}`
empty formatter. The **series** is a list of integers indicating which quantum number goes to which empty formatter. In
the former case in tag 203, this implies that the 0th (1st) QN number in the CAT file gets assigned to Jup, the 1st (2nd) QN
number gets assigned to Kup, and so on and so forth. The **tag** is just a string for the built-in GUI that specifies to
the user which style to use.

Now, consider the second entry in the tuple.

Here, **fmt** is an empty string and **series** is a list with a single integer. An empty **fmt** string and a single-element
list in **series** tells the routine that you need a more advanced formatting scheme that might depend on the specific values
of the quantum numbers. The value contained in the single-element **series** list specifies which of these custom formatting
schemes to use.

In order to program a new, advanced conditional formatting scheme, consider the code starting with `elif fmt_idx == 203:`
later in the format_it() function. Note that the first *if* statement asks if `customChoice == 0`. This 0 is associated with
the 0 contained in the single-element **series** list in the dictionary described earlier.

Therefore, if you would like to add a new conditional formatting scheme for QN tag 203, you would then add the following code
after `elif fmt_idx == 203`:

`if customChoice==1:
    (conditional statements regarding the formatting go here. See code for exmaples.)`

and make sure to add to `fmt_dict` a new entry in the tuple keyed as 203:

`203: (... , ... , {'fmt':'', 'series':[1], 'tag': 'New example conditional scheme for tag 203.'})`

The QNFormat routine will then format the quantum numbers appropriately.