# Splatalogue Update Scripts
###### Author: Nathan A. Seifert

This package contains a number of tools used to update portions of the Splatalogue database. Although a number of
tools are featured here, the main script -- run.py -- features a GUI with helper menus for a small set of common tasks.

### Installation

*THIS PACKAGE REQUIRES LINUX. DOES NOT WORK ON WINDOWS SINCE I NEVER WANTED TO DEAL WITH MYSQL HANDLING IN WINDOWS. IF YOU CAN
GET MYSQLDB TO WORK IN WINDOWS, THIS CODE WILL PROBABLY RUN.*

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

### Toyama notes

Submitting data from the Toyama Microwave Atlas is slightly different. The Toyama routine requires
the raw HTML file of the table output from a search on ToyaMA. To facilitate this, just do a single
molecule search from 0 to an arbitrarily high frequency on the target molecule of choice, right click the results
file in your favorite browser, and save to HTML. The ToyaMA routine will first ask you to supply this HTML file.

At the moment, the ToyaMA routine only submits entries as a single rovibrational state of the given molecule,
so all vibrational states will be submitted into a single species.

Entry of quantum number style formatting is also slightly different. After inputting the HTML file  for the table,
the program will ask you to input two sequences corresponding to the string format style of the quantum numbers,
as well as the quantum number ORDERING you desire. Spaces for individual quantum numbers in the style formatter are
written as `{}`. Ordering is represented by a comma-delimited sequence of strings of the form "upN" or "lowN" where N is the integer corresponding to the representative upper state / lower state quantum
number in the ToyaMA entry listing, respectively.

Example:

1. H2O
    - Toyama specifies QNs as J'Ka'Kc' - J''Ka''Kc'' as Uqn2, Uqn3, Uqn4 - Lqn2, Lqn3, Lqn4
    - A QN style of J(Ka, Kc) - J(Ka, Kc) is equivalent to the QN style formatter: `{}({}, {}) - {}({}, {})`
    - The ordering for the above formatter would be inputted as: `up2, up3, up4, low2, low3, low4`
2. NHD
    - Toyama specifies QNs as N'KaKc as N_KaKc, J', F1', F2', F as U/Lqn2, 3, 4, 5
    - Inputted QN style of `N(K<sub>a</sub>, K<sub>c) = {}({}, {}) - {}({}, {}), J = {} - {}, F<sub>1</sub> = {} - {}, F<sub>2</sub> = {} - {}, F = {} - {}`
    - Ordering of above formatted is inputted as: `up2, low2, up3, low3, up4, low4, up5, low5` (Note: ToyaMA QNs of the form N_IJ are automatically formatted to N(I, J) by the program)

Metadata for Toyama can be inputted with the same metadata input files used for JPL/CDMS. If you would like to provide the reference
information in a plaintext file to be read by the program, please enter the path directly into the `Ref1` or `Ref2` entry boxes. The program will automatically
read in the reference information from the specified file.

