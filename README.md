# PyBlame
Browse Git history of a file by navigating using 'blame' annotations.  Written in PyQt4 and Python 2.7.

This program provides an interactive, visual wrapper for the Git blame command.

It allows you to browse the history of a file with line-by-line annotations about the last time each line was modified.  Double- clicking on a line will show the version at the commit point the line was modified, and double-clicking again shows the version before it was modified.

To install, ensure that Python 2.7 and PyQt4 are installed on your system:

Mac:
$ brew install python2.7 pyqt

Linux:
$ sudo apt-get install python2.7 python-qt4
