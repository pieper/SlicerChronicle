import unittest
import os, couchdb, json, urllib, tempfile
import dicom
from __main__ import vtk, qt, ctk, slicer

#
# SlicerChronicle
#

class SlicerChronicle:
  def __init__(self, parent):
    parent.title = "SlicerChronicle" # TODO make this more human readable by adding spaces
    parent.categories = ["Informatics"]
    parent.dependencies = []
    parent.contributors = ["Steve Pieper (Isomics)"] # replace with "Firstname Lastname (Org)"
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
    self.stepWatchCheckBox = qt.QCheckBox()
    self.stepWatchCheckBox.checked = 0
    self.stepWatchCheckBox.setToolTip("When enabled, slicer will watch the chronicle db for new series load commands and will download and open the corresponding data.")
    parametersFormLayout.addRow("Watch for Steps to Process", self.stepWatchCheckBox)

    # connections
    self.stepWatchCheckBox.connect('toggled(bool)', self.toggleStepWatch)

    # Add vertical spacer
    self.layout.addStretch(1)

    # make a copy of the logic, which connects us to the database
    # TODO: we should have an option to pick the server, port, database name, and filter
    # and then match up this with an action to perform
    self.logic = SlicerChronicleLogic()

  def cleanup(self):
    self.logic.stopStepWatcher()

  def toggleStepWatch(self,checked):
    if checked:
      self.logic.startStepWatcher()
    else:
      self.logic.stopStepWatcher()

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

    self.operations = {
            "ChronicleStudyRender" : self.chronicleStudyRender,
    }

    # connect to a local instance of couchdb (must be started externally)
    self.couchDB_URL='http://localhost:5984'
    self.couchDB_URL='http://common.bwh.harvard.edu:5984'
    self.databaseName='chronicle'

    # path to Chronicle utility source code
    import os
    self.recordPath = os.path.join(os.environ['HOME'], 'chronicle/Chronicle/bin/record.py')

    # connect to the database and register the changes API callback
    self.couch = couchdb.Server(self.couchDB_URL)
    try:
      self.db = self.couch[self.databaseName]
    except Exception, e:
      import traceback
      traceback.print_exc()

  def startStepWatcher(self):
    self.stopStepWatcher()
    self.changes = CouchChanges(self.db, self.stepWatcherChangesCallback)

  def stopStepWatcher(self):
    if self.changes:
      self.changes.stop()
      self.changes = None

  def stepWatcherChangesCallback(self, db, line):
    try:
      if line != "":
        change = json.loads(line)
        doc = db[change['id']]
        if 'type' in doc.keys() and doc['type'] == 'ch.step':
          print(doc)
          # <Document u'2.25.331237450000223992174473666375979231286'@u'1-d203faeea604bf2690cb26149de46425' {
          #   u'inputs': [[[u'University of Washington', u'IRL Generic DRO'], [u'(20130528) IRL Generic PET/CT', u'1.3.6.1.4.1.150.2.1.1.2.20130529141416']]],
          #   u'name': u'Study Render',
          #   u'parameters': [],
          #   u'outputs': [],
          #   u'desiredProvenance': {
          #     u'application': u'3D Slicer',
          #     u'operation': u'ChronicleStudyRender',
          #     u'version': u'4.3*'
          #   },
          #   u'type': u'ch.step'
          # }>
          #
          # self.fetchAndLoadSeries(doc['seriesUID'])
          if self.canPerformStep(doc):
            operation = doc['desiredProvenance']['operation']
            print("yes, we can do this!!!")
            print("let's %s!" % operation)
            self.operations[operation](doc)
        else:
          print("not a series")
    except Exception, e:
      import traceback
      traceback.print_exc()

  def canPerformStep(self,stepDoc):
    '''Analyze the step document to see if the current
    instance of slicer is able to create a result with
    the desired provenance.  Uses unix wildcard matching
    conventions.'''
    import fnmatch
    prov = stepDoc['desiredProvenance']
    applicationMatch = fnmatch.fnmatch("3D Slicer", prov['application'])
    versionMatch = fnmatch.fnmatch("4.3.1", prov['version'])
    operationMatch = prov['operation'] in self.operations.keys()
    return (applicationMatch and versionMatch and operationMatch)

  def fetchAndLoadSeries(self,seriesUID):
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
      else:
        print('this is not an instance we can load')
    node = None
    if filesToLoad != []:
      status, node = slicer.util.loadVolume(filesToLoad[0], {}, returnNode=True)
    return node

  def fetchAndRenderStudy(self,studyKey):
    """Download the study data from chronicle and make
    a set of secondary captures"""

    # construct the url to fetch the seriesList for this study
    api = "/_design/instances/_view/context?reduce=true"
    args = '&group_level=3'
    args += '&startkey=%s' % json.dumps(studyKey)
    studyKey.append({})
    args += '&endkey=%s' % json.dumps(studyKey)
    seriesListURL = self.db.resource().url + api + args
    studyDescription = studyKey[1][0]

    # get the series list and iterate
    # - each row is a series and the key contains the UID and descriptions
    urlFile = urllib.urlopen(seriesListURL)
    seriesListJSON = urlFile.read()
    seriesList = json.loads(seriesListJSON)
    rows = seriesList['rows']
    orientations = ('Axial', 'Sagittal', 'Coronal')
    studyVolumeNodes = []
    for row in [rows[0],]:
      instanceCount = row['value']
      seriesUID = row['key'][2][2]
      seriesDescription = row['key'][2][1]
      print(seriesUID + ' should have ' + str(instanceCount) + ' instances' )
      seriesVolumeNode = self.fetchAndLoadSeries(seriesUID)
      if seriesVolumeNode:
          studyVolumeNodes.append(seriesVolumeNode)
          for orientation in orientations:
            self.seriesRender(seriesVolumeNode,seriesDescription,orientation=orientation)
    if studyVolumeNodes != []:
      for orientation in orientations:
        self.studyRender(studyVolumeNodes,studyDescription,orientation=orientation)

  def chronicleStudyRender(self,stepDoc):
    """Render each study on the input list"""
    inputs = stepDoc['inputs']
    for input in inputs:
      self.fetchAndRenderStudy(input)

  def saveSliceViews(self,sliceNode,filePath):
    """Frame grab the slice view widgets and save
    them to the given file"""
    slicer.app.processEvents() # wait for a render
    layoutManager = slicer.app.layoutManager()
    sliceWidget = layoutManager.sliceWidget(sliceNode.GetLayoutName())
    pixmap = qt.QPixmap().grabWidget(sliceWidget.parent())
    pixmap.save(filePath)

  def makeAndRecordSecondaryCapture(self,filePaths,seriesDescription,studyReferenceFilePath):
    """Convert the image to a secondary capture associated with
    the given reference DICOM file, then record it in chronicle"""
    import DICOMLib

    # first, run img2dcm to make a dicom secondary capture
    args = ['-k', 'SeriesDescription=%s' % seriesDescription,
            '--study-from', studyReferenceFilePath,
            filePaths[0], filePaths[1]
            ]
    DICOMLib.DICOMCommand('img2dcm', args).start()

    # then run the chronicle record script to upload it
    print( "running %s with %s" % (self.recordPath, [filePaths[1],]) )
    process = qt.QProcess()
    process.start(self.recordPath, [filePaths[1],] )
    process.waitForFinished()
    if process.exitStatus() == qt.QProcess.CrashExit or process.exitCode() != 0:
      stdout = process.readAllStandardOutput()
      stderr = process.readAllStandardError()
      print('exit status is: %d' % process.exitStatus())
      print('exit code is: %d' % process.exitCode())
      print('error is: %d' % process.error())
      print('standard out is: %s' % stdout)
      print('standard error is: %s' % stderr)
      raise( UserWarning("Could not run %s with %s" % (self.recordPath, [filePaths[1],])) )
    print('dicom saved to', filePaths[1])

    # finally attach the original image to the new document
    # - it will have been given a new UID by img2dcm, and that
    #   will be the id used in chronicle
    dataset = dicom.read_file(filePaths[1])
    print('expecting to find', dataset.SOPInstanceUID)
    doc = self.db.get(dataset.SOPInstanceUID)
    print('attempting to attache', filePaths[0])
    fp = open(filePaths[0])
    self.db.put_attachment(doc, fp, 'image.jpg')
    fp.close()

  def seriesRender(self,seriesVolumeNode,seriesDescription,orientation):
    """Make a mosaic with images covering the volume range for
    the given orientation"""
    import CompareVolumes
    compareLogic = CompareVolumes.CompareVolumesLogic()
    sliceNodeByViewName = compareLogic.volumeLightbox(seriesVolumeNode,orientation=orientation)
    referenceFile = seriesVolumeNode.GetStorageNode().GetFileName()
    jpgFilePath = os.path.join(slicer.app.temporaryPath, "%s-%s.jpg" % (orientation, 'seriesRender'))
    self.saveSliceViews(sliceNodeByViewName.values()[0],jpgFilePath)
    dcmFilePath = os.path.join(slicer.app.temporaryPath, "%s-%s.dcm" % (orientation, 'seriesRender'))
    self.makeAndRecordSecondaryCapture((jpgFilePath,dcmFilePath),"Slicer Series Render", referenceFile)

  def studyRender(self,studyVolumeNodes,studyDescription,orientation):
    """Make a mosaic with one viewer for each series in the study"""
    import CompareVolumes
    compareLogic = CompareVolumes.CompareVolumesLogic()
    sliceNodeByViewName = compareLogic.viewerPerVolume(volumeNodes=studyVolumeNodes,orientation=orientation)
    referenceFile = studyVolumeNodes[0].GetStorageNode().GetFileName()
    jpgFilePath = os.path.join(slicer.app.temporaryPath, "%s-%s.jpg" % (orientation, 'seriesRender'))
    self.saveSliceViews(sliceNodeByViewName.values()[0],jpgFilePath)
    dcmFilePath = os.path.join(slicer.app.temporaryPath, "%s-%s.dcm" % (orientation, 'seriesRender'))
    self.makeAndRecordSecondaryCapture((jpgFilePath,dcmFilePath),"Slicer Study Render", referenceFile)

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
      #print('heartbeat')
      pass
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

class SlicerChronicleBrowser:
  """
  A webview based patient/study/series browser
  """

  def __init__(self):
    self.webView = qt.QWebView()

  def webViewCallback(self,qurl):
    url = qurl.toString()
    print(url)
    if url == 'reslicing':
      self.reslicing()
    if url == 'chart':
      self.chartTest()
    pass

  def show(self):
    html = """
    <a href="reslicing">Run reslicing test</a>
    <p>
    <a href="chart">Run chart test</a>
    """
    self.webView.setHtml(html)
    self.webView.settings().setAttribute(qt.QWebSettings.DeveloperExtrasEnabled, True)
    self.webView.page().setLinkDelegationPolicy(qt.QWebPage.DelegateAllLinks)
    self.webView.connect('linkClicked(QUrl)', self.webViewCallback)
    self.webView.show()

class SlicerChronicleContext:
  """
  Methods for operating on the patient/study/series/instance
  dicom composite context via the chronicle api

  based on the ctkDICOMDatabase context api
  https://github.com/commontk/CTK/blob/d8cd14e7cd431732fa80206aadca5e6488417578/Libs/DICOM/Core/ctkDICOMDatabase.h#L132-L142

  and chlib/context.js

  https://github.com/pieper/ch/blob/246a3ab9d7e533f2013b77c4b9afd0124a98b2f3/chlib/context.js#L17-L59
  """

  def __init__(self,db):
    self.db = db

    self._commonOptions = {
      'reduce': 'true',
      'stale': 'update_after',
      'group_level': '',
      'startkey': '',
      'endkey': '',
    }


  def viewList(self,options):
    """Returns the list associated with the passed options"""

    # construct the url to fetch the seriesList for this study
    api = "/_design/instances/_view/context?reduce=%s" % options['reduce']
    if options['reduce'] == 'true':
      args = '&group_level=%s' % options['group_level']
    if options['startkey'] != '':
      args += '&startkey=%s' % json.dumps(options['startkey'])
    if options['endkey'] != '':
      args += '&endkey=%s' % json.dumps(options['endkey'])
    args += '&stale=%s' % options['stale']

    # each row is an entry and the key contains the UID and descriptions
    viewListURL = self.db.resource().url + api + args
    urlFile = urllib.urlopen(viewListURL)
    viewListJSON = urlFile.read()
    viewList = json.loads(viewListJSON)
    if viewList.has_key('rows'):
      return(viewList['rows'])
    else:
      return([])


  def patients(self):
    """returns a list of patients
    patient is a tuple of [institution,mrn]
    """
    options = dict(self._commonOptions)
    options['group_level'] = '1'
    return self.viewList(options)

  def studiesForPatient(self,patient):
    """returns a list of studies
    """
    options = dict(self._commonOptions)
    options['group_level'] = '2'
    options['startkey'] = patient
    options['endkey'] = list(patient)
    options['endkey'].append({})
    return self.viewList(options)

  def seriesForStudy(self,study):
    """returns a list of series
    """
    options = dict(self._commonOptions)
    options['group_level'] = '3'
    options['startkey'] = study
    options['endkey'] = list(study)
    options['endkey'].append({})
    return self.viewList(options)

  def instancesForSeries(self,series):
    """returns a list of instances
    """
    api = "/_design/instances/_view/seriesInstances?reduce=false"
    seriesUID = series[2][2]
    args = '&key="%s"' % seriesUID
    seriesInstancesURL = self.db.resource().url + api + args
    urlFile = urllib.urlopen(seriesInstancesURL)
    instancesJSON = urlFile.read()
    instances = json.loads(instancesJSON)['rows']
    return instances

  def instanceDataset(self,instance):
    """returns a pydicom dataset for the instance
    """
    classUID,instanceUID = instance['value']
    doc = self.db[instanceUID]
    instanceURL = self.db.resource().url + '/' + doc['_id'] + "/object.dcm"
    instanceFileName = doc['_id']
    tmpdir = tempfile.mkdtemp()
    instanceFilePath = os.path.join(tmpdir, instanceFileName)
    urllib.urlretrieve(instanceURL, instanceFilePath)
    ds = dicom.read_file(instanceFilePath)
    return ds


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
    self.test_SlicerChronicleWeb()
    #self.test_SlicerChronicleLogic()

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

  def test_SlicerChronicleLogic(self):
    """
    Test the basic logic of the module for patient/study/series level
    """
    self.delayDisplay("Starting the test",100)

    logic = SlicerChronicleLogic()
    context = SlicerChronicleContext(logic.db)

    # patient
    patients = context.patients()
    self.delayDisplay("There are " + str(len(patients)) + " patients", 200)

    patientZero = patients[0]
    self.delayDisplay("Patient Zero is " + str(patientZero), 200)

    # study
    studies = context.studiesForPatient(patientZero['key'])
    self.delayDisplay("Patient Zero has " + str(len(studies)) + " studies", 200)

    studyZero = studies[0]
    self.delayDisplay("Study Zero is " + str(studyZero), 200)

    # series
    series = context.seriesForStudy(studyZero['key'])
    self.delayDisplay("Study Zero has " + str(len(series)) + " series", 200)

    seriesZero = series[0]
    self.delayDisplay("Series Zero is " + str(seriesZero), 200)

    # instance
    instances = context.instancesForSeries(seriesZero['key'])
    self.delayDisplay("Series Zero has " + str(len(instances)) + " instances", 200)

    # datatset
    instanceZero = instances[0]
    self.delayDisplay("instance Zero is " + str(instanceZero), 200)

    dataset = context.instanceDataset(instanceZero)
    self.delayDisplay("instance Zero is a " + dataset.SOPClassUID + " ", 200)


  def test_SlicerChronicleWeb(self):
    """
    Test the basic Slicer-as-agent approach.
    """

    self.delayDisplay("Starting the test",100)

    browser = SlicerChronicleBrowser()
    browser.show()
    slicer.modules.SlicerChronicleWidget.browser = browser

    dirPath = os.path.dirname(slicer.modules.slicerchronicle.path)
    path = os.path.join(dirPath, "site/index.html")
    url = qt.QUrl("file://" + path)
    browser.webView.setUrl(url)

  def test_changesAndHeartbeat(self):

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
    self.delayDisplay("Waiting... ", 1000)

    changes.stop()

    self.delayDisplay("noticesReceived: %s" % self.noticesReceived)
    self.assertTrue(len(self.noticesReceived) >= 3)


    self.delayDisplay('Test passed!')