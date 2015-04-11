import os
import unittest
import couchdb, couchdb.http
import os, couchdb, json, urllib, tempfile, time
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *

#
# SceneViewer
#

class SceneViewer(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SceneViewer" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Informatics"]
    self.parent.dependencies = []
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
    This module tracks the MRML scene and enters the result in a database for later recall.
    """
    self.parent.acknowledgementText = """
    This module developed by Steve Pieper, Isomics, Inc.  This work is supported by NIH National Cancer Institute (NCI), award U24 CA180918 (QIICR: Quantitative Image Informatics for Cancer Research) and the National Institute of Biomedical Imaging and Bioengineering (NIBIB), award P41 EB015902 (NAC: Neuroimage Analysis Center).
""" # replace with organization, grant and thanks.

#
# SceneViewerWidget
#

class SceneViewerWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # input volume selector
    #
    self.inputSelector = slicer.qMRMLNodeComboBox()
    self.inputSelector.nodeTypes = ( ("vtkMRMLScalarVolumeNode"), "" )
    self.inputSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.inputSelector.selectNodeUponCreation = True
    self.inputSelector.addEnabled = False
    self.inputSelector.removeEnabled = False
    self.inputSelector.noneEnabled = False
    self.inputSelector.showHidden = False
    self.inputSelector.showChildNodeTypes = False
    self.inputSelector.setMRMLScene( slicer.mrmlScene )
    self.inputSelector.setToolTip( "Pick the input to the algorithm." )
    parametersFormLayout.addRow("Input Volume: ", self.inputSelector)

    #
    # output volume selector
    #
    self.outputSelector = slicer.qMRMLNodeComboBox()
    self.outputSelector.nodeTypes = ( ("vtkMRMLScalarVolumeNode"), "" )
    self.outputSelector.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.outputSelector.selectNodeUponCreation = False
    self.outputSelector.addEnabled = True
    self.outputSelector.removeEnabled = True
    self.outputSelector.noneEnabled = False
    self.outputSelector.showHidden = False
    self.outputSelector.showChildNodeTypes = False
    self.outputSelector.setMRMLScene( slicer.mrmlScene )
    self.outputSelector.setToolTip( "Pick the output to the algorithm." )
    parametersFormLayout.addRow("Output Volume: ", self.outputSelector)

    #
    # check box to trigger taking screen shots for later use in tutorials
    #
    self.enableScreenshotsFlagCheckBox = qt.QCheckBox()
    self.enableScreenshotsFlagCheckBox.checked = 0
    self.enableScreenshotsFlagCheckBox.setToolTip("If checked, take screen shots for tutorials. Use Save Data to write them to disk.")
    parametersFormLayout.addRow("Enable Screenshots", self.enableScreenshotsFlagCheckBox)

    #
    # scale factor for screen shots
    #
    self.screenshotScaleFactorSliderWidget = ctk.ctkSliderWidget()
    self.screenshotScaleFactorSliderWidget.singleStep = 1.0
    self.screenshotScaleFactorSliderWidget.minimum = 1.0
    self.screenshotScaleFactorSliderWidget.maximum = 50.0
    self.screenshotScaleFactorSliderWidget.value = 1.0
    self.screenshotScaleFactorSliderWidget.setToolTip("Set scale factor for the screen shots.")
    parametersFormLayout.addRow("Screenshot scale factor", self.screenshotScaleFactorSliderWidget)

    #
    # Apply Button
    #
    self.applyButton = qt.QPushButton("Apply")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    parametersFormLayout.addRow(self.applyButton)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
    self.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputSelector.currentNode() and self.outputSelector.currentNode()

  def onApplyButton(self):
    logic = SceneViewerLogic()
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    screenshotScaleFactor = int(self.screenshotScaleFactorSliderWidget.value)
    print("Run the algorithm")
    logic.run(self.inputSelector.currentNode(), self.outputSelector.currentNode(), enableScreenshotsFlag,screenshotScaleFactor)


#
# SceneViewerLogic
#

class SceneViewerLogic(ScriptedLoadableModuleLogic):
  """Maps mrml scene data and events into couchdb
  """

  def __init__(self, parent=None):
    ScriptedLoadableModuleLogic.__init__(self,parent)

    self.server = None # couchdb.Server
    self.database = None # couchdb.Database
    self.sceneObservers = [] # (eventtype, observertag)
    self.nodeObservers = {} # (eventtype, observertag) by node

    # a scratch scene to use for generating and parsing xml representations
    # of mrml nodes
    self.helperScene = slicer.vtkMRMLScene()
    self.helperScene.SetSaveToXMLString(1)
    self.helperScene.SetLoadFromXMLString(1)

  def timeStamp(self):
    """Return a string of the current time with microsecond resolution"""
    return "%.6f" % time.time()

  def defaultDatabaseName(self):
    hostname = os.uname()[1]
    username = os.getenv('USER')
    dateTime = self.timeStamp()
    return "SceneViewer/%s/%s/%s" % (hostname, username, dateTime)

  def connect(self,server='localhost:5984',database=''):
    """
    Connects the current mrml scene to the SceneViewer database,
    which is a coucbdb instance running at server.  Scene information
    is stored in a database named database or SceneViewer/Hostname/username/DateTime.
    """

    # connect to couchdb instance and database
    if database == '':
      database = self.defaultDatabaseName()
    if not server.startswith('http://'):
      server = 'http://'+server
    self.server = couchdb.Server(server)
    try:
      if not database in self.server:
        self.server.create(database)
      self.db = self.server[database]
    except Exception as e:
      import traceback
      traceback.print_exc()

    if self.db:
      # take an initial snapshot of the scene
      self.reportScene()
      # observe any changes
      self.observeScene()

    return self.db != None

  def disconnect(self):
    """Remove all observers and close connection to database"""
    for event,tag in self.sceneObservers:
      slicer.mrmlScene.RemoveObserver(tag)
    for node in self.nodeObservers.keys():
      node.RemoveObserver(self.nodeObservers[node][1])
    self.database = None
    self.server = None
    self.sceneObservers = []
    self.nodeObservers = {}

  def reportScene(self):
    """Record a document to of the current set of nodes of the scene.
    Also refresh observers to include only the currently present nodes.
    """
    nodeIDsToRecord = []
    previousNodes = self.nodeObservers.keys()
    scene = slicer.mrmlScene
    scene.InitTraversal()
    node = scene.GetNextNode()
    while node:
      nodeID = node.GetID()
      nodeIDsToRecord.append(nodeID)
      if node in self.nodeObservers.keys():
        previousNodes.remove(node)
      else:
        print(('observing', node))
        self.observeNode(node)
      node = scene.GetNextNode()
    for node in previousNodes:
      print(('UNobserving', node))
      # remove any observations for nodes that aren't in the scene
      node.RemoveObserver(self.nodeObservers[node][1])
    document = {
      '_id' : "nodeSet-"+self.timeStamp(),
      'nodeIDs' : nodeIDsToRecord
    }
    self.db.save(document)

  def reportNode(self,node):
    copyNode = self.helperScene.CreateNodeByClass(node.GetClassName())
    if not copyNode:
      print('Warning: %s is is not registered with the scene' % node.GetClassName())
      return
    copyNode.Copy(node)
    self.helperScene.Clear(1)
    self.helperScene.AddNode(copyNode)
    self.helperScene.Commit()
    mrml = self.helperScene.GetSceneXMLString()
    # usually changing the node id is only done by scene,
    # but here we know what we are doing and we want it
    # to be consistent with the original node's id.
    mrml.replace('id="'+node.GetID()+'"', 'id="'+copyNode.GetID()+'"')
    document = {
      '_id' : node.GetID() + "-" + self.timeStamp(),
      'mrml' : mrml
    }
    self.db.save(document)

    # TODO:
    # check for storable nodes and check the modified times
    # of the bulk data relative to the node - may require new
    # method on the nodes to provide the information generically.
    # If the bulk data does need saving, add to a queue that can
    # be processed in the background (possibly skipping frames
    # if data is coming too quickly, then drop any intermediate frames
    # but only save the most recent for a given node).

  def observeScene(self):
    """Add observers to the mrmlScene and also to all the nodes of the scene"""

    scene = slicer.mrmlScene
    tag = scene.AddObserver(scene.NodeAddedEvent, self.onNodeAdded)
    self.sceneObservers.append( (scene.NodeAddedEvent, tag) )
    tag = scene.AddObserver(scene.NodeRemovedEvent, self.onNodeRemoved)
    self.sceneObservers.append( (scene.NodeRemovedEvent, tag) )

    scene.InitTraversal()
    node = scene.GetNextNode()
    while node:
      self.reportNode(node)
      self.observeNode(node)
      node = scene.GetNextNode()

  def observeNode(self,node):
    if node.IsA('vtkMRMLNode'):
      # use AnyEvent since it will catch events like TransformModified
      tag = node.AddObserver(vtk.vtkCommand.AnyEvent, self.onNodeModified)
      self.nodeObservers[node] = (vtk.vtkCommand.ModifiedEvent, tag)
    else:
      raise('should not happen: non node is in scene')

  def onNodeAdded(self,scene,eventName):
    self.reportScene()

  def onNodeRemoved(self,node,eventName):
    self.reportScene()

  def onNodeModified(self,node,eventName):
    self.reportNode(node)


class SceneViewerTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_SceneViewer1()

  def test_SceneViewer1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests sould exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test", 50)

    logic = SceneViewerLogic()
    slicer.modules.SceneViewerWidget.logic = logic

    self.assertTrue(
      logic.connect(database="sceneviewertest")
    )

    self.delayDisplay('Test passed!')
