import unittest
import os, json, urllib, tempfile, md5, logging
import couchdb
import dicom
from __main__ import vtk, qt, ctk, slicer
from DICOMLib import DICOMUtils
from DICOMLib import DICOMDetailsPopup
import EditorLib
from EditorLib.EditUtil import EditUtil

# global for all demos
default_couchDB_URL='http://quantome.org:5984'

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
    self.stepWatchCheckBox.setToolTip("When enabled, slicer will watch the chronicle chronicleDB for new series load commands and will download and open the corresponding data.")
    parametersFormLayout.addRow("Watch for Steps to Process", self.stepWatchCheckBox)

    # qiicr view demo button
    self.qiicrViewButton = qt.QPushButton("View Demo")
    self.stepWatchCheckBox.setToolTip("Run a demo of quantitative imaging results.")
    parametersFormLayout.addRow("QIICR", self.qiicrViewButton)


    # connections
    self.stepWatchCheckBox.connect('toggled(bool)', self.toggleStepWatch)
    self.qiicrViewButton.connect('clicked()', self.qiicrViewDemo)

    # Add vertical spacer
    self.layout.addStretch(1)

    # make a copy of the logic, which connects us to the database
    # TODO: we should have an option to pick the server, port, database name, and filter
    # and then match up this with an action to perform
    self.logic = SlicerChronicleLogic(default_couchDB_URL)

  def cleanup(self):
    self.logic.stopStepWatcher()

  def toggleStepWatch(self,checked):
    if checked:
      self.logic.startStepWatcher()
    else:
      self.logic.stopStepWatcher()

  def qiicrViewDemo(self):
    """A demo of looking at quantitative imaging results"""

    qiicrIowaURL = "https://s3.amazonaws.com/IsomicsPublic/qiicr-iowa.json"
    qiicrIowaMD5 = "977e88f901fbd01be275ce9ddce787f5"

    logging.info('downloading qiicrIowa data')
    urlFile = urllib.urlopen(qiicrIowaURL)
    qiicrIowaJSON = urlFile.read()
    md5er = md5.new()
    md5er.update(qiicrIowaJSON)
    if qiicrIowaMD5 != md5er.hexdigest():
      logging.error("Invalid download of qiicrIowaJSON: md5 doesn't match!")
      logging.error(qiicrIowaMD5 + " does not equal " + md5er.hexdigest() )
      raise Exception('could not download')

    qiicrIowa = json.loads(qiicrIowaJSON)
    slicer.modules.qiicrIowa = qiicrIowa
    logging.info("downloaded qiicrIowa data")

    patientIDs = set()
    personObserverNames = set()
    for index in range(len(qiicrIowa)):
      measurement = qiicrIowa[index]
      patientIDs.add(measurement['patientID'])
      personObserverNames.add(measurement['personObserverName'])
    print(patientIDs)
    print(personObserverNames)

    # originalDatabaseDirectory = self.logic.operatingDICOMDatabase('qiicrView')

    measurement0 = qiicrIowa[0]

    referencedSegmentSOPInstanceUID = measurement0["referencedSegmentSOPInstanceUID"]

    studyUID = self.logic.studyUIDforInstanceUID(referencedSegmentSOPInstanceUID)

    instanceURLs = self.logic.studyInstanceURLs(studyUID)
    self.logic.fetchAndIndexInstanceURLs(instanceURLs)

    detailsPopup = DICOMDetailsPopup()
    detailsPopup.offerLoadables(studyUID, 'Study')
    detailsPopup.examineForLoading()
    detailsPopup.loadCheckedLoadables()


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
  def __init__(self,couchDB_URL,chronicleDatabaseName='chronicle', operationDatabaseName='segmentation-server'):

    self.chronicleDatabaseName=chronicleDatabaseName
    self.operationDatabaseName=operationDatabaseName
    # dicom classes associated with images we can display
    self.imageClasses = [
              "1.2.840.10008.5.1.4.1.1.2", # CT Image
              "1.2.840.10008.5.1.4.1.1.4", # MR Image
              "1.2.840.10008.5.1.4.1.1.128", # PET Image
              ]
    self.changes = None

    self.operations = {
            "Load" : self.chronicleLoad,
            "ChronicleStudyRender" : self.chronicleStudyRender,
            "LesionSegmenter" : self.chronicleLesionSegmenter,
    }
    self.activeRequestID = None


    # path to Chronicle utility source code
    import os
    self.recordPath = os.path.join(os.environ['HOME'], 'chronicle/Chronicle/bin/record.py')

    # connect to the database and register the changes API callback
    self.couch = couchdb.Server(couchDB_URL)
    try:
      self.operationDB = self.couch[self.operationDatabaseName]
    except Exception, e:
      import traceback
      traceback.print_exc()

    try:
      self.chronicleDB = self.couch[self.chronicleDatabaseName]
    except Exception, e:
      import traceback
      traceback.print_exc()

  def startStepWatcher(self):
    self.stopStepWatcher()
    self.changes = CouchChanges(self.operationDB, self.stepWatcherChangesCallback)

  def stopStepWatcher(self):
    if self.changes:
      self.changes.stop()
      self.changes = None

  def stepWatcherChangesCallback(self, operationDB, line):
    try:
      if line != "":
        change = json.loads(line)
        doc = operationDB[change['id']]
        if 'type' in doc.keys() and doc['type'] == 'ch.step':
          print(doc)
          if 'status' in doc.keys() and doc['status'] == 'open':
            if self.canPerformStep(doc):
              operation = doc['desiredProvenance']['operation']
              print("yes, we can do this!!!")
              print("let's %s!" % operation)
              self.activeRequestID = change['id']
              self.operations[operation](doc)
              self.activeRequestID = None
    except Exception, e:
      import traceback
      traceback.print_exc()

  def postStatus(self,status, progressString):
      print(self.activeRequestID, status, progressString)
      try:
        id_, rev = self.operationDB.save({
          'requestID' : self.activeRequestID,
          'type' : status,
          'progress' : progressString,
        })
        return (id_,rev)
      except:
        print('...failed to save progress!!!')

  def canPerformStep(self,stepDoc):
    '''Analyze the step document to see if the current
    instance of slicer is able to create a result with
    the desired provenance.  Uses unix wildcard matching
    conventions.'''
    import fnmatch
    prov = stepDoc['desiredProvenance']
    applicationMatch = fnmatch.fnmatch("3D Slicer", prov['application'])
    versionMatch = fnmatch.fnmatch(slicer.app.applicationVersion, prov['version'])
    operationMatch = prov['operation'] in self.operations.keys()
    return (applicationMatch and versionMatch and operationMatch)

  def fetchAndLoadSeriesArchetype(self,seriesUID):
    tmpdir = tempfile.mkdtemp()

    api = "/_design/instances/_view/seriesInstances?reduce=false"
    args = '&key="%s"' % seriesUID
    seriesInstancesURL = self.chronicleDB.resource().url + api + args
    urlFile = urllib.urlopen(seriesInstancesURL)
    instancesJSON = urlFile.read()
    instances = json.loads(instancesJSON)
    logging.info("Got the following response for seriesUID " + seriesUID + str(instances))
    filesToLoad = []
    if len(instances['rows']) == 0:
      logging.warn("No instances associated with seriesUID %s" % seriesUID)
    for instance in instances['rows']:
      classUID,instanceUID = instance['value']
      if classUID in self.imageClasses:
        doc = self.chronicleDB[instanceUID]
        print("need to download ", doc['_id'])
        instanceURL = self.chronicleDB.resource().url + '/' + doc['_id'] + "/object.dcm"
        instanceFileName = doc['_id']
        instanceFilePath = os.path.join(tmpdir, instanceFileName)
        urllib.urlretrieve(instanceURL, instanceFilePath)
        filesToLoad.append(instanceFilePath);
      else:
        print('this instance is not a class we can load: %s' % classUID)
    node = None
    if filesToLoad != []:
      status, node = slicer.util.loadVolume(filesToLoad[0], {}, returnNode=True)
    return node

  def fetchAndIndexInstanceURLs(self,instanceURLs):
    tmpdir = tempfile.mkdtemp()
    instanceFilePath = os.path.join(tmpdir, 'instance.dcm')
    for instanceURL in instanceURLs:
      urllib.urlretrieve(instanceURL, instanceFilePath)
      self.postStatus('progress', "Inserting %s" % instanceURL)
      slicer.dicomDatabase.insert(instanceFilePath)

  def operatingDICOMDatabase(self,operation):
    """Specify a database to use for the tagged operation (directory name)
    Only open a new one if it differs from the currently selected database
    """
    tempDatabaseDir = slicer.app.temporaryPath + '/' + operation
    if tempDatabaseDir != os.path.split(slicer.dicomDatabase.databaseFilename)[0]:
      originalDatabaseDirectory = DICOMUtils.openTemporaryDatabase(tempDatabaseDir, absolutePath=True)
      return originalDatabaseDirectory
    else:
      return tempDatabaseDir

  def volumeNodeBySeriesUID(self, inputSeriesUID):
    """Check to see if the series is already loaded as a node.
    If not, check in the database and try to load from there"""
    seriesVolumeNode = None

    return seriesVolumeNode

  def fetchAndLoadInstanceURLs(self,instanceUIDURLPairs, seriesUID):
    tmpdir = tempfile.mkdtemp()

    filesToLoad = []
    for instanceUID,instanceURL in instanceUIDURLPairs:
      filePath = slicer.dicomDatabase.fileForInstance(instanceUID)
      if filePath != '' and os.access(filePath, os.F_OK):
        self.postStatus('progress', "Already in database: %s as %s" % (instanceUID, filePath))
      else:
        instanceFileName = "object-%d.dcm" % len(filesToLoad)
        instanceFilePath = os.path.join(tmpdir, instanceFileName)
        filesToLoad.append(instanceFilePath)
        self.postStatus('progress', "Downloading %s to %s" % (instanceURL, instanceFilePath))
        urllib.urlretrieve(instanceURL, instanceFilePath)
        self.postStatus('progress', "Inserting %s" % instanceUID)
        slicer.dicomDatabase.insert(instanceFilePath)
      self.postStatus('progress', "Downloaded %d of %d" % (len(filesToLoad), len(instanceUIDURLPairs)))

    detailsPopup = DICOMDetailsPopup()
    detailsPopup.offerLoadables(seriesUID, 'Series')
    detailsPopup.examineForLoading()
    detailsPopup.loadCheckedLoadables()

    seriesUIDTag = "0020,000e"
    for volumeNode in slicer.util.getNodes('vtkMRMLScalarVolumeNode*').values():
      instanceUIDs = volumeNode.GetAttribute('DICOM.instanceUIDs')
      if instanceUIDs and instanceUIDs != '':
        uid0 = instanceUIDs.split()[0]
        if slicer.dicomDatabase.instanceValue(uid0, seriesUIDTag) == seriesUID:
          return volumeNode
    return None

  def studyUIDforInstanceUID(self,instanceUID):
    """Pulls down the instance and gets the studyUID from it"""
    doc = self.chronicleDB.get(instanceUID)
    try:
      return doc['dataset']['0020000D']['Value']
    except KeyError:
      return None

  def studyInstanceURLs(self,studyUID):
    """Return the urls of all instances that have this studyUID"""
    instanceURLs = []
    # construct the url to fetch the seriesList for this study
    api = "/_design/tags/_view/byTagAndValue?reduce=false"
    studyUIDTag = "0020000D"
    key = [studyUIDTag, studyUID]
    args = '&startkey=%s' % json.dumps(key)
    key.append({})
    args += '&endkey=%s' % json.dumps(key)
    instanceListURL = self.chronicleDB.resource().url + api + args

    # get the instance list and iterate
    # - each row is an instanceUID
    urlFile = urllib.urlopen(instanceListURL)
    instanceListJSON = urlFile.read()
    instanceList = json.loads(instanceListJSON)
    rows = instanceList['rows']
    for row in rows:
      instanceURL = self.chronicleDB.resource().url + "/" + row['id'] + "/object.dcm"
      instanceURLs.append(instanceURL)
    return instanceURLs

  def fetchAndRenderStudy(self,studyKey):
    """Download the study data from chronicle and make
    a set of secondary captures"""

    # construct the url to fetch the seriesList for this study
    api = "/_design/instances/_view/context?reduce=true"
    args = '&group_level=3'
    args += '&startkey=%s' % json.dumps(studyKey)
    studyKey.append({})
    args += '&endkey=%s' % json.dumps(studyKey)
    seriesListURL = self.chronicleDB.resource().url + api + args
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
      seriesVolumeNode = self.fetchAndLoadSeriesArchetype(seriesUID)
      if seriesVolumeNode:
          studyVolumeNodes.append(seriesVolumeNode)
          for orientation in orientations:
            self.seriesRender(seriesVolumeNode,seriesDescription,orientation=orientation)
    if studyVolumeNodes != []:
      for orientation in orientations:
        self.studyRender(studyVolumeNodes,studyDescription,orientation=orientation)

  def indexDICOMDirectory(self,path):
    for root, subFolders, files in os.walk(path):
      for file_ in files:
        filePath = os.path.join(root,file_)
        slicer.dicomDatabase.insert(filePath)

  def chronicleLoad(self,stepDoc):
    """Load the study from inputData
    Required parts of stepDoc:
        { "desiredProvenance": {
               "inputData": [
                 {
                   "studyUID": "<studyUID>",
                   "dataFormat": "zip",
                   "dataURL": "http://<path to zip file>",
                   "dataToken": "token",
                } ] } } """
    slicer.util.showStatusMessage('Processing load request...')
    inputData = stepDoc['desiredProvenance']['inputData'][0]
    if inputData['dataFormat'] != 'zip':
      print("Cannot load non-zip data")
      return;
    zipTmpDir = tempfile.mkdtemp()
    zipFilePath = os.path.join(zipTmpDir, "study.zip")
    print('downloading', inputData['dataURL'], zipFilePath)
    slicer.util.showStatusMessage('Downloading study zip...')

    try:
      import requests
      headers = {}
      if inputData['dataToken'] != "":
        headers['Authorization'] = 'bearer ' + inputData['dataToken']
      response = requests.get(inputData['dataURL'], headers=headers)
      chunkCount = 0
      if(response.ok):
        with open(zipFilePath, 'wb') as fd:
          for chunk in response.iter_content(chunk_size=1024*128):
            fd.write(chunk)
            slicer.util.showStatusMessage('Downloading chunk %d...' % chunkCount)
            chunkCount += 1
      else:
        print(response.reason)
        slicer.util.showStatusMessage('Could not download')
        return
    except ImportError:
      urllib.urlretrieve(inputData['dataURL'], zipFilePath)

    dicomTmpDir = tempfile.mkdtemp()
    slicer.app.applicationLogic().Unzip(zipFilePath, dicomTmpDir)
    slicer.util.showStatusMessage('Unzipping study...')
    print('Unzip', zipFilePath, dicomTmpDir)
    slicer.util.showStatusMessage('Processing DICOM...')
    self.indexDICOMDirectory(dicomTmpDir)
    detailsPopup = DICOMDetailsPopup()
    detailsPopup.offerLoadables(inputData['studyUID'], 'Study')
    detailsPopup.examineForLoading()
    slicer.util.showStatusMessage('Loading Study...')
    detailsPopup.loadCheckedLoadables()
    slicer.util.showStatusMessage('Study Loaded...')


  def chronicleStudyRender(self,stepDoc):
    """Render each study on the input list"""
    inputs = stepDoc['inputs']
    for input in inputs:
      self.fetchAndRenderStudy(input)

  def fetchAndSegmentSeries(self,instanceUIDURLPairs, inputSeriesUID, seedInstanceUID, seed):
    """Download the study data from given URL and segment based on seed point.
    Re-upload the result.
    Currently a demo that depends on having CIP and Reporting installed.
    """

    try:
      import CIP_LesionModel
    except ImportError:
      self.postStatus('result', 'Lesion segmentation not available')
      return

    try:
      slicer.modules.encodeseg
    except ImportError:
      self.postStatus('result', 'DICOM SEG encoding not available')
      return

    self.postStatus('progress', 'loading')
    seriesVolumeNode = self.volumeNodeBySeriesUID(inputSeriesUID)
    if not seriesVolumeNode:
      seriesVolumeNode = self.fetchAndLoadInstanceURLs(instanceUIDURLPairs, inputSeriesUID)
    if seriesVolumeNode:
      slicer.util.delayDisplay('got it!',100)
    else:
      self.postStatus('result', 'Could not get access to the series')
      return

    #
    # calculate the RAS coordinate of the seed and place a fiducial
    # - seed is in 0-1 slice space of seedInstanceUID (origin is upper left)
    #
    imagePositionPatientTag = '0020,0032'
    imageOrientationPatientTag = '0020,0037'
    rowsTag = '0028,0010'
    columsTag = '0028,0011'
    spacingTag = '0028,0030'
    positionLPS = map(float, slicer.dicomDatabase.instanceValue(seedInstanceUID, imagePositionPatientTag).split('\\'))
    orientationLPS = map(float, slicer.dicomDatabase.instanceValue(seedInstanceUID, imageOrientationPatientTag).split('\\'))
    spacing = map(float, slicer.dicomDatabase.instanceValue(seedInstanceUID, spacingTag).split('\\'))
    rows = float(slicer.dicomDatabase.instanceValue(seedInstanceUID, rowsTag))
    colums = float(slicer.dicomDatabase.instanceValue(seedInstanceUID, columsTag))
    pixelSeed = [seed[0] * colums, seed[1] * rows]
    orientationLPS = map(float, slicer.dicomDatabase.instanceValue(seedInstanceUID, imageOrientationPatientTag).split('\\'))
    position = [-1. * positionLPS[0], -1. * positionLPS[1], positionLPS[2]]

    # here slice spacing doesn't come into play because seed is in plane of seedInstanceUID
    row = [-1. * spacing[0] * orientationLPS[0], -1. * spacing[0] * orientationLPS[1], orientationLPS[2]]
    column = [-1. * spacing[1] * orientationLPS[3], -1. * spacing[1] * orientationLPS[4], orientationLPS[5]]
    seedRAS = [ position[0] + pixelSeed[0] * row[0] + pixelSeed[1] * column[0],
                position[1] + pixelSeed[0] * row[1] + pixelSeed[1] * column[1],
                position[2] + pixelSeed[0] * row[2] + pixelSeed[1] * column[2] ]

    markupsLogic = slicer.modules.markups.logic()
    fiducialIndex = markupsLogic.AddFiducial(*seedRAS)
    fiducialID = markupsLogic.GetActiveListID()
    fiducialNode = slicer.mrmlScene.GetNodeByID(fiducialID)
    self.postStatus('progress', 'Placed seed at RAS %s' % seedRAS)


    #
    # Run the lesion segmentation module
    #
    lesionLevelsetNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLScalarVolumeNode")
    lesionLevelsetNode.SetName('LesionLevelSet')
    slicer.mrmlScene.AddNode(lesionLevelsetNode)

    parameters = {}
    print("Calling CLI...")
    parameters["inputImage"] = seriesVolumeNode.GetID()
    parameters["outputLevelSet"] = lesionLevelsetNode.GetID()
    parameters["seedsFiducials"] = fiducialID
    parameters["maximumRadius"] = 30 ;# TODO: make this a parameter
    parameters["fullSizeOutput"] = True ;# TODO: what does this mean?

    module = slicer.modules.generatelesionsegmentation
    self.postStatus('progress', 'Running lesion segmenter')
    result = slicer.cli.runSync(module, None, parameters)
    self.postStatus('progress', 'Lesion segmenter completed')

    #
    # threshold in the Editor
    #
    volumesLogic = slicer.modules.volumes.logic()
    lesionLabelNode = volumesLogic.CreateAndAddLabelVolume( slicer.mrmlScene, lesionLevelsetNode, lesionLevelsetNode.GetName() + '-label' )
    colorNode = slicer.util.getNode('GenericAnatomyColors')
    lesionLabelNode.GetDisplayNode().SetAndObserveColorNodeID(colorNode.GetID())
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActiveVolumeID( lesionLevelsetNode.GetID() )
    selectionNode.SetReferenceActiveLabelVolumeID( lesionLabelNode.GetID() )
    slicer.app.applicationLogic().PropagateVolumeSelection(0)

    slicer.util.selectModule('Editor')
    slicer.util.delayDisplay('Entered Editor', 100)
    toolsBox = slicer.modules.EditorWidget.toolsBox
    helper = slicer.modules.EditorWidget.helper
    toolsBox.selectEffect('ThresholdEffect')
    thresholdTool = toolsBox.currentTools[0]
    thresholdTool.min = 0.
    thresholdTool.max = lesionLevelsetNode.GetImageData().GetScalarRange()[1]
    thresholdTool.apply()
    slicer.util.delayDisplay('Thresholded', 100)
    toolsBox.selectEffect('DefaultTool')

    lesionLabelNode.SetName(seriesVolumeNode.GetName() + "-label")
    helper.setVolumes(seriesVolumeNode, lesionLabelNode)
    helper.structureListWidget.split()
    EditUtil.exportAsDICOMSEG(seriesVolumeNode)
    self.postStatus('progress', 'Exported SEG to database')

    segmentationFile = None
    modalityTag = "0008,0060"
    studyUID = slicer.dicomDatabase.studyForSeries(inputSeriesUID)
    if studyUID:
      for serie in slicer.dicomDatabase.seriesForStudy(studyUID):
        file0 = slicer.dicomDatabase.filesForSeries(serie)[0]
        if file0:
          if slicer.dicomDatabase.fileValue(file0, modalityTag) == "SEG":
            # TODO: delete old SEG objects
            segmentationFile = file0
            break

    sliceNodes = slicer.util.getNodes('vtkMRMLSliceNode*')
    for sliceNode in sliceNodes.values():
      sliceNode.JumpSliceByCentering(*seedRAS)

    #
    # attach screenshot and seg object
    #
    slicer.util.delayDisplay('Saving Pixmap...', 200)
    id_, rev = self.postStatus('progress', 'saving pixmap')
    pixmap = qt.QPixmap().grabWidget(slicer.util.mainWindow())
    tmpdir = tempfile.mkdtemp()
    imagePath = os.path.join(tmpdir,'image.png')
    pixmap.save(imagePath)
    doc = self.operationDB.get(id_)
    fp = open(imagePath,'rb')
    self.operationDB.put_attachment(doc, fp, "image.png")
    fp.close()
    imageURL = self.couch.resource().url + "/" + self.operationDatabaseName + "/" + id_ + "/image.png"
    segURL = "Unknown"
    if segmentationFile:
      fp = open(segmentationFile,'rb')
      self.operationDB.put_attachment(doc, fp, "object.SEG.dcm")
      fp.close()
      segURL = self.couch.resource().url + "/" + self.operationDatabaseName + "/" + id_ + "/object.SEG.dcm"

    html = '''
        <img id="resultImage" width=200 src="%(imageURL)s">
        <a href="%(segURL)s">Download Segmentation</a>
    ''' % {
          'imageURL' : imageURL,
          'segURL' : segURL,
    }
    self.postStatus('result', html)

  def chronicleLesionSegmenter(self,stepDoc):
    """Perform the segmentation process based on the data"""
    inputInstanceUIDURLPairs = stepDoc['desiredProvenance']['inputInstanceUIDURLPairs']
    inputSeriesUID = stepDoc['desiredProvenance']['inputSeriesUID']
    seedInstanceUID = stepDoc['desiredProvenance']['seedInstanceUID']
    seed = stepDoc['desiredProvenance']['seed']
    stepDoc['status'] = 'working'
    self.operationDB.save(stepDoc)
    originalDatabaseDirectory = self.operatingDICOMDatabase('LesionSegmenter')
    self.fetchAndSegmentSeries(inputInstanceUIDURLPairs, inputSeriesUID, seedInstanceUID, seed)
    DICOMUtils.openDatabase(originalDatabaseDirectory)

    stepDoc['status'] = 'closed'
    self.operationDB.save(stepDoc)

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
    doc = self.chronicleDB.get(dataset.SOPInstanceUID)
    print('attempting to attache', filePaths[0])
    fp = open(filePaths[0])
    self.chronicleDB.put_attachment(doc, fp, 'image.jpg')
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

  def __init__(self,chronicleDB):
    self.chronicleDB = chronicleDB

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
    viewListURL = self.chronicleDB.resource().url + api + args
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
    seriesInstancesURL = self.chronicleDB.resource().url + api + args
    urlFile = urllib.urlopen(seriesInstancesURL)
    instancesJSON = urlFile.read()
    instances = json.loads(instancesJSON)['rows']
    return instances

  def instanceDataset(self,instance):
    """returns a pydicom dataset for the instance
    """
    classUID,instanceUID = instance['value']
    doc = self.chronicleDB[instanceUID]
    instanceURL = self.chronicleDB.resource().url + '/' + doc['_id'] + "/object.dcm"
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
    self.test_SlicerChronicleLogic()

  def changesCallback(self,chronicleDB,line):
    try:
      self.noticesReceived.append(line)
      self.delayDisplay('got "%s" change from %s' % (line,chronicleDB))
      if line != "":
        change = json.loads(line)
        doc = chronicleDB[change['id']]
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

    logic = SlicerChronicleLogic(default_couchDB_URL)
    context = SlicerChronicleContext(logic.chronicleDB)

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
    chronicleDatabaseName='chronicle'

    # connect to the database and register the changes API callback
    couch = couchdb.Server(default_couchDB_URL)
    chronicleDB = couch[chronicleDatabaseName]
    changes = CouchChanges(chronicleDB, self.changesCallback)

    # insert a document
    document = {
        'comment': 'a test of SlicerChronicle',
    }
    doc_id, doc_rev = chronicleDB.save(document)
    self.delayDisplay("Saved %s,%s" %(doc_id, doc_rev))

    # should get a notification of our document, along with two heartbeat messages
    # (may also get other notices if the database is active)
    self.delayDisplay("Waiting... ", 1000)

    changes.stop()

    self.delayDisplay("noticesReceived: %s" % self.noticesReceived)
    self.assertTrue(len(self.noticesReceived) >= 3)

    self.delayDisplay('Test passed!')


  def test_chronicleLoad(self):
    '''
    import SlicerChronicle; SlicerChronicle.SlicerChronicleTest().test_chronicleLoad()
    '''

    logic = SlicerChronicleLogic('http://quantome.org:5984', 'chronicle', 'operations')
    logic.startStepWatcher()

    # connect to the database and register the changes API callback
    couch = couchdb.Server('http://quantome.org:5984')
    operationsDB = couch['operations']

    # a representative document that should always load
    document = {
       "status": "open",
       "type": "ch.step",
       "desiredProvenance": {
           "operation": "Load",
           "application": "3D Slicer",
           "version": "4.*",
           "inputData": [
             {
               "user": "c2FyYWguZmllbGRzQHdpbmR5dmFsbGV5LmNvbQ==",
               "studyUID": "1.3.6.1.4.1.14519.5.2.1.2744.7002.271803936741289691489150315969",
               "dataFormat": "zip",
               "dataURL": "https://s3.amazonaws.com/IsomicsPublic/SampleData/QIN-HEADNECK-01-0024-CT.zip",
               "dataToken": "",
            }
          ]
       }
    }
    # this one worked during the 25 minute window when the dataToken was valid
    exampleTeamplayDocument = {
       "status": "open",
       "type": "ch.step",
       "desiredProvenance": {
           "operation": "Load",
           "application": "3D Slicer",
           "version": "4.*",
           "inputData": [
             {
               "studyUID": "2.14.22.1.488611267051454857277203743926733063549507",
               "dataFormat": "zip",
               "dataURL": "https://instanceaccess-service-teamplay-himss-us-east.azurewebsites.net/api/pic/DownloadStudy/DownloadStudyZip?tenantId=2&userId=c2FyYWguZmllbGRzQHdpbmR5dmFsbGV5LmNvbQ==&studyTenantId=3&uniqueStudyId=3362&studyInstanceUid=2.14.22.1.488611267051454857277203743926733063549507",
               "dataToken": "eyJ0eXAiOiJKV1QiLCJhbGciOiJodHRwOi8vd3d3LnczLm9yZy8yMDAwLzA5L3htbGRzaWcjcnNhLXNoYTEifQ.eyJ1cG4iOiJzYXJhaC5maWVsZHNAd2luZHl2YWxsZXkuY29tIiwiVGVuYW50SWQiOiIyIiwiVUlkIjoiN2EyOTg5MWMtZGY4MC00ODFiLWE0NmYtZjcyODlkMTQ0YzkwIiwicm9sZSI6Ikluc3RpdHV0aW9uQWRtaW4iLCJUZW5hbnRTZXJpYWxOdW1iZXIiOiIxMTA2NDQyMC0xMDAxMDAiLCJpc3MiOiJ0ZWFtcGxheSBBdXRoIFNlcnZlciIsImF1ZCI6InRlYW1wbGF5IFdlYiBDbGllbnQiLCJleHAiOjE0ODY0MDAzODgsIm5iZiI6MTQ4NjM5ODg4OH0.tiJoIcqb7DDYvn-CEU7XdyWMDAUNHmzXARYdwDsZyZ0v-9lA6a5Rxv0FlS28VStY-2ANJ1FeekBgBzVisoi1xwq98Hv018_Sw_IsLelWPlgbxjFDfY5WfPSinY6nibTrNFl4neJRPRXJK0hWla4VT_qC1TuiPS2l2b1dN14MtjQPEroi9ODQ71927MgEUfLEb6gZrXbdPnXersFUMku2pTyB2Lgf21zBo7_OjNxGTbewce_2PbTu9RVi8hVk48Wx6dvQ2AFks0jkmA_zyMeFgUX5p8W9zTIHtl2oVxjBk4SE7oFepm-xsVk36xg7JT53uKppnUgN4VOyr5ZSUddA8nCu_R2rYKDO2esEZa0EH5gUZxVYUPYpjpqSQdEbgVlTPkxMdf8eclQP-MrqG_Zt5TisvB150kJN9ariiqFeKVYLzWXxq4BLdKSLpwtdRHHXLg5XmJmlplZ8LUZryJojXoGcMqauX1xUyjTtUFI-En6otomMhhmjnKLJaiVq_xF-",}
          ]
       }
    }

    exampleTeamplayUsers = """
Sarah Fields: c2FyYWguZmllbGRzQHdpbmR5dmFsbGV5LmNvbQ==
Chris Winter: Y2hyaXMud2ludGVyQG1vdW50YWluc3ByaW5ncy5jb20=
"""

    doc_id, doc_rev = operationsDB.save(document)
    slicer.util.delayDisplay('Submitting request...',100)

    qt.QTimer.singleShot(1000,logic.stopStepWatcher)
