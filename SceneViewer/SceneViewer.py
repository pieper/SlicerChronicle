import os
import unittest
import os, json, urllib, tempfile, time
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


    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass

#
# SceneViewerLogic
#

class SceneViewerLogic(ScriptedLoadableModuleLogic):
  """Maps mrml scene data and events into json
  """

  def __init__(self, parent=None):
    ScriptedLoadableModuleLogic.__init__(self,parent)

    self.sceneObservers = [] # (eventtype, observertag)
    self.nodeObservers = {} # (eventtype, observertag) by node

    # a scratch scene to use for generating and parsing xml representations
    # of mrml nodes
    self.helperScene = slicer.vtkMRMLScene()
    self.helperScene.SetSaveToXMLString(1)
    self.helperScene.SetLoadFromXMLString(1)

    self.emitCallback = None

  def timeStamp(self):
    """Return a string of the current time with microsecond resolution"""
    return "%.6f" % time.time()

  def defaultDatabaseName(self):
    hostname = os.uname()[1]
    username = os.getenv('USER')
    dateTime = self.timeStamp()
    return "SceneViewer/%s/%s/%s" % (hostname, username, dateTime)

  def disconnect(self):
    """Remove all observers and close connection to database"""
    for event,tag in self.sceneObservers:
      slicer.mrmlScene.RemoveObserver(tag)
    for node in self.nodeObservers.keys():
      node.RemoveObserver(self.nodeObservers[node][1])
    self.sceneObservers = []
    self.nodeObservers = {}

  def emit(self,document):
    if self.emitCallback:
      self.emitCallback(document)

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
    self.emit(document)

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
    self.emit(document)

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

    self.messageDelay = 50
    self.delayDisplay("Starting the test")

    logic = SceneViewerLogic()
    slicer.modules.SceneViewerWidget.logic = logic

    webWindow = qt.QWidget()
    layout = qt.QVBoxLayout()
    webWindow.setLayout(layout)

    self.eventCount = 0
    self.eventCountLabel = qt.QLabel('Event count: 0')
    layout.addWidget(self.eventCountLabel)

    #
    # try pouchdb in QtWebKit
    # - requires pouch with polyfill for function bind
    #

    webView = qt.QWebView()
    webView.settings().setAttribute(qt.QWebSettings.DeveloperExtrasEnabled, True)
    webView.settings().setAttribute(qt.QWebSettings.OfflineStorageDatabaseEnabled, True)
    webView.settings().setAttribute(qt.QWebSettings.LocalStorageEnabled, True)
    webView.settings().setAttribute(qt.QWebSettings.LocalContentCanAccessRemoteUrls, True)
    webView.settings().setAttribute(qt.QWebSettings.LocalContentCanAccessFileUrls, True)
    webView.settings().setOfflineStoragePath('/tmp')

    import os
    appPath = os.path.join(slicer.modules.sceneviewer.path, "../../app/index.html")

    jar = qt.QNetworkCookieJar()
    nam = qt.QNetworkAccessManager()
    nam.setCookieJar(jar)
    page = webView.page()
    page.setNetworkAccessManager(nam)
    self.mainFrame = page.mainFrame()
    webView.setUrl(qt.QUrl('file://' + appPath))
    layout.addWidget(webView)
    webWindow.show()

    slicer.util.jar = jar
    slicer.util.nam = nam
    slicer.util.webWindow = webWindow
    slicer.util.page = webView.page()

    self.delayDisplay('Should have browser window now')
    page.action(qt.QWebPage.SelectStartOfDocument).trigger()

    slicer.util.inspectAction = page.action(qt.QWebPage.InspectElement)
    slicer.util.inspectAction.trigger()

    self.delayDisplay('Should have inspector window now')

    databaseName = logic.defaultDatabaseName()

    def storeInPouch(doc):
      javascriptCode = """
        document.db.put( %(doc)s ).catch(function (error) {
          console.log("Error saving to pouchdb", error);
        });
      """ % {
        'doc' : json.dumps(doc)
      }
      self.mainFrame.evaluateJavaScript(javascriptCode)
      self.eventCount += 1
      self.eventCountLabel.text = 'Event count: %d' % self.eventCount

    logic.emitCallback = storeInPouch

    # take an initial snapshot of the scene
    logic.reportScene()
    # observe any changes
    logic.observeScene()

    mainFrame.evaluateJavaScript("document.db.allDocs({include_docs : true}).then(function(result) {console.log(result);})")

    self.delayDisplay('Test passed!')
