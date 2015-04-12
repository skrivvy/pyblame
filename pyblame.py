#!/usr/bin/python
####################################################################
# PyBlame
#
# This program provides an interactive, visual wrapper for the Git
# blame command.
#
# It allows you to browse the history of a file with line-by-line
# annotations about the last time each line was modified.  Double-
# clicking on a line will show the version at the commit point the
# line was modified, and double-clicking again shows the version
# before it was modified.
#
# To install, ensure that Python 2.7 and PyQt4 are installed on your
# system:
#
# Mac:
# $ brew install python2.7 pyqt
#
# Linux:
# $ sudo apt-get install python2.7 python-qt4
#
#
#
####################################################################


import sys
import os
import glob
import string
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import QtGui
from subprocess import *
import shutil
import time


####################################################################
def trace(method):

    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        print('== %r (%r, %r) %2.2f sec' % (method.__name__, args, kw, te-ts))
        return result

    return timed

####################################################################
class GitModel(QObject):

    # Signals
    fileChanged = pyqtSignal()
    revChanged = pyqtSignal()

    def __init__(self, parent=None, *args):
        QObject.__init__(self, parent, *args)

        # Fields
        self.branch = "HEAD"
        self.filename = None
        self.description = None
        self.lines = []
        self.revs = []
        self.revIdx = -1
        self.sha = None
        self.abbrev = None
        self.firstDiff = None

    def setFile( self, filein ):
        self.filename = filein
        print "setting filename: " + self.filename
        self.loadRevs()
        self.setRev(len(self.revs) - 1)
        self.fileChanged.emit()

    def setRev( self, rev ):
        if rev == self.revIdx or rev < 0 or rev >= len(self.revs):
            return
        print "setting rev: " + str(rev)
        self.revIdx = rev
        self.sha = self.revs[self.revIdx]
        self.abbrev = self.sha[0:8]
        self.loadBlame()
        self.loadDescription()
        self.revChanged.emit()

    def setSha(self, sha):
        index = 0
        print "setting sha: " + sha
        for rev in self.revs:
            if rev.startswith(sha):
                self.setRev(index)
            break
            index += 1
        if index == len(self.revs):
            print "couldn't find sha in log: " + sha

    def loadRevs(self):
        if self.filename == None:
            self.revs = []
        else:
            self.revs = self.execResultAsList(["git", "rev-list", "--reverse", self.branch, str(self.filename)])

    def loadBlame(self):
        if self.filename != None and self.revIdx >= 0:
            self.lines = self.execResultAsList(["git", "blame", str(self.filename), self.revs[self.revIdx]])

            # Find the index of the first line that changed in the current sha
            self.firstDiff = None
            index = 0
            for line in self.lines:
                if line.startswith(self.abbrev):
                    self.firstDiff = index
                    break
            index += 1

    def loadDescription(self):
        if self.filename != None and self.revIdx >= 0:
            self.description = self.execResultAsString(["git", "show", "--quiet", self.revs[self.revIdx]])

    @trace
    def execResultAsString(self, command):
        output = check_output(command)
        return output

    def execResultAsList2(self, command):
        commandStr = " ".join(command)
        p = Popen(commandStr, shell=True, stdout=PIPE, stderr=PIPE)
        output = []
        for line in p.stdout:
            output.append(line.strip())
        return output

    @trace
    def execResultAsList(self, command):
        result = check_output(command)
        lines = result.splitlines()
        return lines


####################################################################
class DescriptionTextEdit(QTextEdit):
    def __init__(self, git, parent=None):
        QTextEdit.__init__(self, parent)
        self.git = git
        self.setCurrentFont(QFont('Courier'))
        self.connect(self.git, SIGNAL("revChanged()"), self.handleRevChanged)

    def sizeHint(self):
        return QSize(400,200)

    def handleRevChanged(self):
        self.setText(self.git.description)


####################################################################
class BlameListView(QListView):

    def setModel(self, model):
        QListView.setModel(self, model)
        self.connect(model, SIGNAL("requestScroll(QModelIndex)"), self.handleRequestScroll)

    def mouseDoubleClickEvent(self, ev):
        QListView.mouseDoubleClickEvent(self, ev)
        index = self.currentIndex()
        if index != None:
            index.model().invokeAction(index)

    def handleRequestScroll(self, index):
        print "scrolling to: " + str(index.row())
        self.scrollTo(index)


####################################################################
class RevisionSlider(QSlider):
    def __init__(self, git, parent=None):
        QSlider.__init__(self, Qt.Horizontal, parent)
        self.git = git
        self.setFocusPolicy(Qt.NoFocus)
        self.setTracking(False)
        self.setTickPosition(QSlider.TicksBothSides)
        self.setTickInterval(1)
        self.connect(self.git, SIGNAL("fileChanged()"), self.handleModelChanged)
        #self.connect(self.git, SIGNAL("revChanged()"), self.handleModelChanged)
        self.connect(self, SIGNAL("valueChanged(int)"), self.handleValueChanged)
        self.handleModelChanged()

    def handleModelChanged(self):
        self.setMaximum(len(self.git.revs) - 1)
        self.setMinimum(0)
        print "slider update value: " + str(self.git.revIdx)
        self.setValue(self.git.revIdx)

    def handleValueChanged(self, value):
        print "slider value changed: " + str(value)
        self.git.setRev(value)


####################################################################
class MyListModel(QAbstractListModel):

    # Signals
    requestScroll = pyqtSignal(QModelIndex)

    def __init__(self, git, parent=None, *args):
        QAbstractListModel.__init__(self, parent, *args)
        self.git = git
        self.connect(self.git, SIGNAL("revChanged()"), self.handleRevChanged)

    def rowCount(self, parent=QModelIndex()):
        return len(self.git.lines)

    def data(self, index, role):
        if not index.isValid():
            return QVariant()
        elif role == Qt.DisplayRole:
            return QVariant(self.git.lines[index.row()])
        elif role == Qt.BackgroundRole:
            if (self.git.lines[index.row()].startswith(self.git.abbrev)):
                return QBrush(QColor(0xFF99FF99))
        elif role == Qt.FontRole:
            return QFont('courier')
        return QVariant()

    def handleRevChanged(self):
        print "resetting list model"
        self.reset()
        if self.git.firstDiff != None:
            print "request scroll to: " + str(self.git.firstDiff)
            self.requestScroll.emit(self.index(self.git.firstDiff))

    def invokeAction(self, index):
        if index.isValid():
            sha = self.git.lines[index.row()][0:8]
            if self.git.abbrev == sha:
                if self.git.revIdx > 0:
                    # if you click a line that changed in the current diff,
                    # show the previous version
                    self.git.setRev(self.git.revIdx - 1)
            else:
                # show the version when the line was changed
                self.git.setSha(sha)


####################################################################
class MyWindow(QMainWindow):
    def __init__(self, filein, *args):
        QWidget.__init__(self, *args)

        # create the model
        self.git = GitModel(self)
        self.model = MyListModel(self.git, self)

        # create the list
        lv = BlameListView()
        lv.setModel(self.model)
        self.setCentralWidget(lv)

        # create the output console
        self.model.output = DescriptionTextEdit(self.git, self)
        self.model.output.setReadOnly(True)
        dock = QDockWidget("Description", self);
        dock.setWidget( self.model.output )
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        slider = RevisionSlider(self.git, self)
        dock = QDockWidget("Revisions", self);
        dock.setWidget(slider)
        self.addDockWidget(Qt.TopDockWidgetArea, dock)

        # populate the model
        self.git.setFile( filein )

        # create menu items
        openAct = QAction("&Open...", self)
        openAct.setShortcut("Ctrl+O")
        openAct.setStatusTip("Open a file")
        self.connect(openAct, SIGNAL("triggered()"), self.git.setFile)

        quitAct = QAction("&Quit", self)
        quitAct.setShortcut("Ctrl+Q")
        quitAct.setStatusTip("Quit PyBlame")
        self.connect(quitAct, SIGNAL("triggered()"), SLOT("close()"))

        fileMenu = self.menuBar().addMenu("&File")
        fileMenu.addAction( openAct )
        fileMenu.addSeparator()
        fileMenu.addAction( quitAct )

        # set the size and position of main window
        self.resize(1600,1200)
        self.center()

    def center(self):
        screen = QtGui.QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width()-size.width())/2, (screen.height()-size.height())/2)

    def openFile(self):
        default = self.model.filename
        if default == None:
            default = '/home/'
        filename = QFileDialog.getOpenFileName(self, "Open File", os.path.dirname(str(default)))
        if os.path.exists(filename):
            self.setFile( filename )

    def setFile(self, filename ):
        title = "PyBlame"
        if filename != None:
            title = title+" - "+os.path.basename(str(filename))
            self.model.setFile( filename )
            self.centralWidget().setModel(self.model)
        self.setWindowTitle(title)

    def commandComplete(self):
        if self.dialog != None:
            self.dialog.accept()
            self.dialog = None


####################################################################
def main():
    app = QApplication(sys.argv)

    # execute command and parse the output
    filename = None
    if len(sys.argv) > 1:
      filename = sys.argv[1]

    w = MyWindow(filename)
    #w.setWindowIcon()
    w.show()
    result = app.exec_()

    sys.exit(result)


####################################################################
if __name__ == "__main__":
    main()
