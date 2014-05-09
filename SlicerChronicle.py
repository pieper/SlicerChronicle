import unittest
from __main__ import vtk, qt, ctk, slicer
import os, couchdb, json, urllib, tempfile

#
# SlicerChronicle
#

class SlicerChronicle:
  def __init__(self, parent):
    parent.title = "SlicerChronicle" # TODO make this more human readable by adding spaces
    parent.categories = ["Examples"]
    parent.dependencies = []
    parent.contributors = ["Jean-Christophe Fillion-Robin (Kitware), Steve Pieper (Isomics)"] # replace with "Firstname Lastname (Org)"
    parent.helpText = """
    This is an example of scripted loadable module bundled in an extension.
    """
    parent.acknowledgementText = """
    This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc. and Steve Pieper, Isomics, Inc.  and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.
    self.parent = parent

    # Add this test to the SelfTest module's list for discovery when the module
    # is created.  Since this module may be discovered before SelfTests itself,
    # create the list if it doesn't already exist.
    try:
      slicer.selfTests
    except AttributeError:
      slicer.selfTests = {}
    slicer.selfTests['SlicerChronicle'] = self.runTest

  def runTest(self):
    tester = SlicerChronicleTest()
    tester.runTest()

#
# qSlicerChronicleWidget
#

class SlicerChronicleWidget:
  def __init__(self, parent = None):
    if not parent:
      self.parent = slicer.qMRMLWidget()
      self.parent.setLayout(qt.QVBoxLayout())
      self.parent.setMRMLScene(slicer.mrmlScene)
    else:
      self.parent = parent
    self.layout = self.parent.layout()
    if not parent:
      self.setup()
      self.parent.show()

  def setup(self):
    # Instantiate and connect widgets ...

    #
    # Reload and Test area
    #
    reloadCollapsibleButton = ctk.ctkCollapsibleButton()
    reloadCollapsibleButton.text = "Reload && Test"
    self.layout.addWidget(reloadCollapsibleButton)
    reloadFormLayout = qt.QFormLayout(reloadCollapsibleButton)

    # reload button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadButton = qt.QPushButton("Reload")
    self.reloadButton.toolTip = "Reload this module."
    self.reloadButton.name = "SlicerChronicle Reload"
    reloadFormLayout.addWidget(self.reloadButton)
    self.reloadButton.connect('clicked()', self.onReload)

    # reload and test button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadAndTestButton = qt.QPushButton("Reload and Test")
    self.reloadAndTestButton.toolTip = "Reload this module and then run the self tests."
    reloadFormLayout.addWidget(self.reloadAndTestButton)
    self.reloadAndTestButton.connect('clicked()', self.onReloadAndTest)

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # check box to turn on series watching
    #
    self.seriesWatchCheckBox = qt.QCheckBox()
    self.seriesWatchCheckBox.checked = 0
    self.seriesWatchCheckBox.setToolTip("When enabled, slicer will watch the chronicle db for new series load commands and will download and open the corresponding data.")
    parametersFormLayout.addRow("Watch for Series", self.seriesWatchCheckBox)

    # connections
    self.seriesWatchCheckBox.connect('toggled(bool)', self.toggleSeriesWatch)

    # Add vertical spacer
    self.layout.addStretch(1)

    # make a copy of the logic, which connects us to the database
    # TODO: we should have an option to pick the server, port, database name, and filter
    # and then match up this with an action to perform
    self.logic = SlicerChronicleLogic()

  def cleanup(self):
    self.logic.stopSeriesWatcher()

  def toggleSeriesWatch(self,checked):
    if checked:
      self.logic.startSeriesWatcher()
    else:
      self.logic.stopSeriesWatcher()

  def onReload(self,moduleName="SlicerChronicle"):
    """Generic reload method for any scripted module.
    ModuleWizard will subsitute correct default moduleName.
    """
    globals()[moduleName] = slicer.util.reloadScriptedModule(moduleName)

  def onReloadAndTest(self,moduleName="SlicerChronicle"):
    try:
      self.onReload()
      evalString = 'globals()["%s"].%sTest()' % (moduleName, moduleName)
      tester = eval(evalString)
      tester.runTest()
    except Exception, e:
      import traceback
      traceback.print_exc()
      qt.QMessageBox.warning(slicer.util.mainWindow(),
          "Reload and Test", 'Exception!\n\n' + str(e) + "\n\nSee Python Console for Stack Trace")


#
# SlicerChronicleLogic
#

class SlicerChronicleLogic:
  """
  """
  def __init__(self):

    # dicom classes associated with images we can display
    self.imageClasses = [
              "1.2.840.10008.5.1.4.1.1.2", # CT Image
              "1.2.840.10008.5.1.4.1.1.4", # MR Image
              ]
    self.changes = None

    # connect to a local instance of couchdb (must be started externally)
    self.couchDB_URL='http://localhost:5984'
    self.databaseName='chronicle'
   
    # connect to the database and register the changes API callback
    self.couch = couchdb.Server(self.couchDB_URL)
    self.db = self.couch[self.databaseName]

  def startSeriesWatcher(self):
    self.stopSeriesWatcher()
    self.changes = CouchChanges(self.db, self.seriesWatcherChangesCallback)

  def stopSeriesWatcher(self):
    if self.changes:
      self.changes.stop()
      self.changes = None

  def seriesWatcherChangesCallback(self, db, line):
    try:
      if line != "":
        change = json.loads(line)
        doc = db[change['id']]
        if 'seriesUID' in doc.keys():
          self.downloadAndLoadSeries(doc['seriesUID'])
        else:
          print("not a series")
    except Exception, e:
      import traceback
      traceback.print_exc()

  def downloadAndLoadSeries(self,seriesUID):
    import DICOMScalarVolumePlugin
    import DICOMLib
    tmpdir = tempfile.mkdtemp()

    api = "/_design/instances/_view/seriesInstances?reduce=false"
    args = '&key="%s"' % seriesUID
    seriesInstancesURL = self.db.resource().url + api + args
    urlFile = urllib.urlopen(seriesInstancesURL)
    instancesJSON = urlFile.read()
    instances = json.loads(instancesJSON) 
    filesToLoad = []
    for instance in instances['rows']:
      classUID,instanceUID = instance['value']
      if classUID in self.imageClasses:
        doc = self.db[instanceUID]
        print("need to download ", doc['_id'])
        instanceURL = self.db.resource().url + '/' + doc['_id'] + "/object.dcm"
        instanceFileName = doc['_id']
        instanceFilePath = os.path.join(tmpdir, instanceFileName)
        urllib.urlretrieve(instanceURL, instanceFilePath)
        filesToLoad.append(instanceFilePath);
    slicer.util.loadVolume(filesToLoad[0])


class CouchChanges:
  """Use the changes API of couchdb to 
  trigger actions in slicer
  """

  def __init__(self,db,callback,filter=None):
    self.db = db
    self.callback = callback
    self.filter = filter

    update_seq = db.info()['update_seq']
    api = "/_changes?feed=continuous"
    args = "&since=%d" % update_seq
    args += "&heartbeat=5000"
    self.couchChangesURL = db.resource().url + api + args
    self.start()

  def onSocketNotify(self,fileno):
    line = self.changesSocket.readline().strip()
    if line == "":
      # heartbeat
      print('heartbeat')
    self.callback(self.db,line)

  def start(self):
    """start a connection to the continuous feed of 
    couchdb changes.
    """
    try:
      self.changesSocket = urllib.urlopen(self.couchChangesURL)
    except IOError as e:
      print('Got an IOError trying to connect to the database')

    socketFileNumber = self.changesSocket.fp.fileno()
    self.notifier = qt.QSocketNotifier(socketFileNumber, qt.QSocketNotifier.Read)
    self.notifier.connect('activated(int)', self.onSocketNotify)

  def stop(self):
    self.changesSocket.close()
    self.notifier = None

class SlicerChronicleTest(unittest.TestCase):
  """
  This is the test case for your scripted module.
  """

  def delayDisplay(self,message,msec=1000):
    """This utility method displays a small dialog and waits.
    This does two things: 1) it lets the event loop catch up
    to the state of the test so that rendering and widget updates
    have all taken place before the test continues and 2) it
    shows the user/developer/tester the state of the test
    so that we'll know when it breaks.
    """
    print(message)
    self.info = qt.QDialog()
    self.infoLayout = qt.QVBoxLayout()
    self.info.setLayout(self.infoLayout)
    self.label = qt.QLabel(message,self.info)
    self.infoLayout.addWidget(self.label)
    qt.QTimer.singleShot(msec, self.info.close)
    self.info.exec_()

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_SlicerChronicle1()

  def changesCallback(self,db,line):
    try:
      self.noticesReceived.append(line)
      self.delayDisplay('got "%s" change from %s' % (line,db))
      if line != "":
        change = json.loads(line)
        doc = db[change['id']]
        self.delayDisplay(doc)
        self.assertTrue('comment' in doc.keys())
    except Exception, e:
      import traceback
      traceback.print_exc()
      self.delayDisplay('Exception in callback!')

  def test_SlicerChronicle1(self):
    """ 
    Test the basic Slicer-as-agent approach.
    """

    self.delayDisplay("Starting the test")
    self.noticesReceived = []

    # connect to a local instance of couchdb (must be started externally)
    couchDB_URL='http://localhost:5984'
    databaseName='chronicle'
   
    # connect to the database and register the changes API callback
    couch = couchdb.Server(couchDB_URL)
    db = couch[databaseName]
    changes = CouchChanges(db, self.changesCallback)

    # insert a document
    document = {
        'comment': 'a test of SlicerChronicle',
    }
    doc_id, doc_rev = db.save(document)
    self.delayDisplay("Saved %s,%s" %(doc_id, doc_rev))

    # should get a notification of our document, along with two heartbeat messages
    # (may also get other notices if the database is active)
    self.delayDisplay("Waiting... ", 10100)

    changes.stop()

    self.delayDisplay("noticesReceived: %s" % self.noticesReceived)
    self.assertTrue(len(self.noticesReceived) >= 3)

    self.delayDisplay('Test passed!')
