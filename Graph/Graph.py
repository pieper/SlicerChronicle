import csv
import numpy
import os
import pandas
import pydicom
import random
import unittest
import os, json, urllib, tempfile, time
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *

#
# Graph
#

class Graph(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Graph"
    self.parent.categories = ["Informatics"]
    self.parent.dependencies = []
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"]
    self.parent.helpText = """
    This uses MRML to graph data
    """
    self.parent.acknowledgementText = """
    This module developed by Steve Pieper, Isomics, Inc.  This work is supported by NIH National Cancer Institute (NCI), award 5R01CA235589 (Lymph Node Quantification System for Multisite Clinical Trials) and the National Institute of Biomedical Imaging and Bioengineering (NIBIB), award P41 EB015902 (NAC: Neuroimage Analysis Center).
"""

#
# GraphWidget
#

class GraphWidget(ScriptedLoadableModuleWidget):
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
# Card
#
class Card:
  """textured text to use as captions
     Accept HTML and css!
  """

  def __init__(self, htmlText):

    label = qt.QLabel(htmlText) 
    cardImage = label.grab().toImage()
    cardImage.save("/tmp/card.png")

    planeSource = vtk.vtkPlaneSource()
    planeSource.SetPoint1(-1*label.width,0,0)
    planeSource.SetPoint2(0,0,label.height)
    planeSource.Update()
    cardNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    cardNode.SetName("Text Card")
    cardNode.SetAndObservePolyData(planeSource.GetOutputDataObject(0))

    cardNode.CreateDefaultDisplayNodes()
    cardDisplayNode = cardNode.GetDisplayNode()
    cardDisplayNode.SetAmbient(1)
    cardDisplayNode.SetDiffuse(0)
    cardDisplayNode.SetSpecular(0)

    cardImageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(cardImage, cardImageData)
    append = vtk.vtkImageAppend()
    append.SetInputDataObject(cardImageData)
    cardNode.GetDisplayNode().SetTextureImageDataConnection(append.GetOutputPort())

#
# Page
#
class Page:
  """ Texture from web widget
  """

  def __init__(self, url, size=(1024,768)):
    self.webWidget = slicer.qSlicerWebWidget()
    self.webWidget.size = qt.QSize(*size)
    self.webWidget.url = url
    self.webWidget.connect("loadFinished(bool)", self.onLoaded)

  def onLoaded(self, ok):
    if not ok:
      print(f"Could not load {self.webWidget.url}")
      return
    webPixmap = self.webWidget.grab()
    webPixmap.save("/tmp/page.png")
    print("saved /tmp/page.png")

    return

    # convert the image to vtk, then to png from there
    cardImageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(cardImage, cardImageData)

    planeSource = vtk.vtkPlaneSource()
    planeSource.SetPoint1(20,0,0)
    planeSource.SetPoint2(0,10*len(text),0)
    planeSource.Update()
    cardNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    cardNode.SetName("Text Card")
    cardNode.SetAndObservePolyData(planeSource.GetOutputDataObject(0))
    cardNode.CreateDefaultDisplayNodes()

    modelsDM = slicer.app.layoutManager().threeDWidget(0).threeDView().displayableManagerByClassName('vtkMRMLModelDisplayableManager')
    actor = modelsDM.GetActorByID(cardNode.GetDisplayNode().GetID())
    mapper = actor.GetMapper()
    texture = vtk.vtkTexture()
    texture.SetInterpolate(True)
    texture.SetMipmap(True)
    texture.SetQualityTo32Bit()
    texture.SetInputData(cardImageData)
    actor.SetTexture(texture)




#
# GraphLogic
#

class GraphLogic(ScriptedLoadableModuleLogic):
  """Maps mrml scene data and events into json
  """

  def __init__(self, parent=None):
    ScriptedLoadableModuleLogic.__init__(self,parent)

    self.baseSize = 300
    halfSize = self.baseSize/2
    self.origin = (-1 * halfSize, 0, -1 * halfSize)

  @staticmethod
  def tagStringToDescription(tagString):
    tagValue = int(tagString.replace(",",""), 16)
    tag = pydicom.tag.Tag(tagValue)
    if pydicom.datadict.dictionary_has_tag(tag):
      return pydicom.datadict.dictionary_description(tag)
    else:
      return tagString

  def markupsFromTags(self, tagNames=None):
    markupsDM = slicer.app.layoutManager().threeDWidget(0).threeDView().displayableManagerByClassName('vtkMRMLMarkupsDisplayableManager')
    self.tagNames = tagNames or list(map(self.tagStringToDescription, self.tagStrings))
    self.axisNodes = {}
    axisOffset = 0
    axisStep = self.baseSize / (len(self.tagNames)-1)
    for tagName in self.tagNames:
      axisNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLMarkupsLineNode())
      axisNode.SetName(tagName)
      axisNode.GetDisplayNode().SetPropertiesLabelVisibility(False)
      x = self.origin[0]+axisOffset
      startPoint = (x, 0, self.origin[1])
      endPoint = (x, 0, self.origin[1]+self.baseSize)
      axisNode.AddControlPoint(vtk.vtkVector3d(startPoint))
      axisNode.AddControlPoint(vtk.vtkVector3d(endPoint))
      axisOffset += axisStep
      self.axisNodes[tagName] = axisNode
      # set the shader
      widget = markupsDM.GetWidget(axisNode.GetDisplayNode())
      actors = vtk.vtkPropCollection()
      widget.GetRepresentation().GetActors(actors)
    comment = '''
      for actorIndex in range(actors.GetNumberOfItems()):
        actor = actors.GetItemAsObject(actorIndex)
        shaderProperty = actor.GetShaderProperty()
        fragmentUniforms = shaderProperty.GetFragmentCustomUniforms()
        fragmentUniforms.SetUniform3f("colorFromSteve", [.5,.5,0])
        fragmentUniforms.SetUniform3f("startPoint", startPoint)
        fragmentUniforms.SetUniform3f("endPoint", endPoint)
        shaderProperty.ClearAllShaderReplacements()
        shaderProperty.AddVertexShaderReplacement(
              "//VTK::Light::Dec",  # replace the light block
              False,                 # after the standard replacements
              """
              //VTK::Light::Dec
              out vec4 vertexMCforFrag;

              """,
              False # only do it once
        )
        shaderProperty.AddVertexShaderReplacement(
              "//VTK::Light::Impl",  # replace the light block
              False,                 # after the standard replacements
              """
              //VTK::Light::Impl
              vertexMCforFrag = vertexMC;

              """,
              False # only do it once
        )
        shaderProperty.AddFragmentShaderReplacement(
              "//VTK::TMap::Dec",  # replace the texture map block
              False,                 # after the standard replacements
              """
              //VTK::TMap::Dec
              in vec4 vertexMCforFrag;

              """,
              False # only do it once
        )
        shaderProperty.AddFragmentShaderReplacement(
              "//VTK::Light::Impl",  # replace the light block
              False,                 # after the standard replacements
              """
              //VTK::Light::Impl

              //fragOutput0.rgb = opacity * vec3(ambientColor + diffuse + specular);
              fragOutput0.rgb = colorFromSteve;

              if (false) { 
                opacity = 1. - (clamp((1. - abs(normalVCVSOutput.z)), 0., 1.) / 4.);
              }

              if (false) {
                // https://en.wikipedia.org/wiki/Distance_from_a_point_to_a_line#Vector_formulation
                vec3 n = normalize(endPoint - startPoint);
                vec3 a = startPoint;
                vec3 p = vertexMCforFrag.xyz;
                float distToLine = length((a-p) - dot(a-p, n) * n);
                fragOutput0.a = distToLine;
              }

              if (false) {
                fragOutput0.a = distance(vertexMCforFrag.xyz, startPoint) / distance(startPoint, endPoint);
              }

              """,
              False # only do it once
        )
    '''

  def textureGrid(self, rows=1, columns=20):
    plane = vtk.vtkPlaneSource()
    plane.SetOrigin(self.origin)
    halfSize = self.baseSize/2
    plane.SetPoint1(self.origin[0]+self.baseSize, self.origin[1], self.origin[2])
    plane.SetPoint2(self.origin[0], self.origin[1], self.origin[2]+self.baseSize)
    plane.Update()
    gridNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    gridNode.SetAndObservePolyData(plane.GetOutputDataObject(0))
    gridNode.CreateDefaultDisplayNodes()
    x = self.origin[0]
    startPoint = (x, 0, self.origin[1])
    endPoint = (x, 0, self.origin[1]+self.baseSize)

    modelsDM = slicer.app.layoutManager().threeDWidget(0).threeDView().displayableManagerByClassName('vtkMRMLModelDisplayableManager')
    actor = modelsDM.GetActorByID(gridNode.GetDisplayNode().GetID())
    mapper = actor.GetMapper()
    mapper.MapDataArrayToVertexAttribute(
        "textureCoordinates", "TextureCoordinates", vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS);
    shaderProperty = actor.GetShaderProperty()
    fragmentUniforms = shaderProperty.GetFragmentCustomUniforms()
    fragmentUniforms.SetUniformf("lineCount", 50)
    shaderProperty.ClearAllShaderReplacements()
    shaderProperty.AddVertexShaderReplacement(
          "//VTK::Light::Dec",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Dec
          in vec2 textureCoordinates;
          out vec2 interpolatedTextureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddVertexShaderReplacement(
          "//VTK::Light::Impl",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Impl
          interpolatedTextureCoordinates = textureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddFragmentShaderReplacement(
          "//VTK::TMap::Dec",  # replace the texture map block
          False,                 # after the standard replacements
          """
          //VTK::TMap::Dec
          in vec2 interpolatedTextureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddFragmentShaderReplacement(
          "//VTK::Light::Impl",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Impl

          fragOutput0.rgb = vec3(0);

          float local = mod(interpolatedTextureCoordinates.x, 1./lineCount);
          fragOutput0.a = pow(1 - abs(0.5 - local), 2);
          fragOutput0.a = interpolatedTextureCoordinates.x / 1./lineCount;

          if (interpolatedTextureCoordinates.y < 0.5) {
            fragOutput0.a = mod(interpolatedTextureCoordinates.x, 1./lineCount);
          } else {
            local = fract(interpolatedTextureCoordinates.x * lineCount);
            fragOutput0.a = pow(1. - abs(0.5 - local),100);
          }

          """,
          False # only do it once
    )


  def lineGrid(self, rows=1, columns=20):
    appendPolyData = vtk.vtkAppendPolyData()
    for column in range(columns):
      line = vtk.vtkLineSource()
      offset = self.baseSize * column / columns
      line.SetPoint1(self.origin[0]+offset, self.origin[1], self.origin[2])
      line.SetPoint2(self.origin[0]+offset, self.origin[1], self.origin[2]+self.baseSize)
      appendPolyData.AddInputConnection(line.GetOutputPort())
    appendPolyData.Update()
    gridNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    gridNode.SetAndObservePolyData(appendPolyData.GetOutputDataObject(0))
    gridNode.CreateDefaultDisplayNodes()
    x = self.origin[0]
    startPoint = (x, 0, self.origin[1])
    endPoint = (x, 0, self.origin[1]+self.baseSize)

    modelsDM = slicer.app.layoutManager().threeDWidget(0).threeDView().displayableManagerByClassName('vtkMRMLModelDisplayableManager')
    actor = modelsDM.GetActorByID(gridNode.GetDisplayNode().GetID())
    mapper = actor.GetMapper()
    mapper.MapDataArrayToVertexAttribute(
        "textureCoordinates", "TextureCoordinates", vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS);
    shaderProperty = actor.GetShaderProperty()
    fragmentUniforms = shaderProperty.GetFragmentCustomUniforms()
    fragmentUniforms.SetUniformf("lineCount", 50)
    shaderProperty.ClearAllShaderReplacements()
    shaderProperty.AddVertexShaderReplacement(
          "//VTK::Light::Dec",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Dec
          in vec2 textureCoordinates;
          out vec2 interpolatedTextureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddVertexShaderReplacement(
          "//VTK::Light::Impl",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Impl
          interpolatedTextureCoordinates = textureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddFragmentShaderReplacement(
          "//VTK::TMap::Dec",  # replace the texture map block
          False,                 # after the standard replacements
          """
          //VTK::TMap::Dec
          in vec2 interpolatedTextureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddFragmentShaderReplacement(
          "//VTK::Light::Impl",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Impl

          fragOutput0.rgb = vec3(0);

          float local = mod(interpolatedTextureCoordinates.x, 1./lineCount);
          fragOutput0.a = pow(1 - abs(0.5 - local), 2);
          fragOutput0.a = interpolatedTextureCoordinates.x / 1./lineCount;

          if (interpolatedTextureCoordinates.y < 0.5) {
            fragOutput0.a = mod(interpolatedTextureCoordinates.x, 1./lineCount);
          } else {
            local = fract(interpolatedTextureCoordinates.x * lineCount);
            fragOutput0.a = pow(1. - abs(0.5 - local),100);
          }

          fragOutput0.rgba = vec4(0,0,0,1);
          """,
          False # only do it once
    )
    slicer.modules.actor = actor

  def polyDataGrid(self, rows=1, columns=20):
    planeSource = vtk.vtkPlaneSource()
    planeSource.SetXResolution(columns)
    planeSource.SetYResolution(rows)
    planeSource.SetOrigin(self.origin)
    halfSize = self.baseSize/2
    planeSource.SetPoint1(self.origin[0]+self.baseSize, self.origin[1], self.origin[2])
    planeSource.SetPoint2(self.origin[0], self.origin[1], self.origin[2]+self.baseSize)
    planeSource.Update()
    gridNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    gridNode.SetAndObservePolyData(planeSource.GetOutputDataObject(0))
    gridNode.CreateDefaultDisplayNodes()
    x = self.origin[0]
    startPoint = (x, 0, self.origin[1])
    endPoint = (x, 0, self.origin[1]+self.baseSize)

    modelsDM = slicer.app.layoutManager().threeDWidget(0).threeDView().displayableManagerByClassName('vtkMRMLModelDisplayableManager')
    actor = modelsDM.GetActorByID(gridNode.GetDisplayNode().GetID())
    mapper = actor.GetMapper()
    slicer.modules.actor = actor

  def gridImageData(self, width, height, rows, columns):
    """return a vtkImageData of the grid"""

    gridImage = qt.QImage(width, height, qt.QImage().Format_ARGB32)
    gridImage.fill(0)

    # a painter to use for various jobs
    painter = qt.QPainter()

    # draw a border around the pixmap
    painter.begin(gridImage)
    pen = qt.QPen()
    color = qt.QColor("#888")
    color.setAlphaF(0.8)
    pen.setColor(color)
    pen.setWidth(3)
    painter.setPen(pen)
    for row in range(1,rows):
      y = height * row//rows
      painter.drawLine(0, y, width, y)
    for column in range(1,columns):
      x = width * column//columns
      painter.drawLine(x, 0, x, height)
    painter.end()

    gridImage.save("/tmp/grid.png")

    # convert the image to vtk, then to png from there
    gridImageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(gridImage, gridImageData)
    return gridImageData

  def mipmapGrid(self, rows=1, columns=20):

    gridImageData = self.gridImageData(1024, 1024, 10, 20)

    planeSource = vtk.vtkPlaneSource()
    planeSource.SetXResolution(columns)
    planeSource.SetYResolution(rows)
    planeSource.SetOrigin(self.origin)
    halfSize = self.baseSize/2
    planeSource.SetPoint1(self.origin[0]+self.baseSize, self.origin[1], self.origin[2])
    planeSource.SetPoint2(self.origin[0], self.origin[1], self.origin[2]+self.baseSize)
    planeSource.Update()
    gridNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    gridNode.SetAndObservePolyData(planeSource.GetOutputDataObject(0))
    gridNode.CreateDefaultDisplayNodes()

    modelsDM = slicer.app.layoutManager().threeDWidget(0).threeDView().displayableManagerByClassName('vtkMRMLModelDisplayableManager')
    actor = modelsDM.GetActorByID(gridNode.GetDisplayNode().GetID())
    mapper = actor.GetMapper()
    texture = vtk.vtkTexture()
    texture.SetInterpolate(True)
    texture.SetMipmap(True)
    texture.SetQualityTo32Bit()
    texture.SetInputData(gridImageData)
    actor.SetTexture(texture)

    slicer.modules.actor = actor

  def lineData(self, lines=100, columns=20, groups=20):
    columnSize = self.baseSize / columns
    appendPolyData = vtk.vtkAppendPolyData()
    for line in range(lines):
      polyLineSource = vtk.vtkPolyLineSource()
      polyLineSource.SetNumberOfPoints(columns)
      value = random.random()
      for column in range(columns):
        line = vtk.vtkLineSource()
        offset = column * columnSize
        polyLineSource.SetPoint(column, self.origin[0]+offset, self.origin[1] + 1, self.origin[2] + value * self.baseSize)
        value += (random.random()-0.5) * .05
      appendPolyData.AddInputConnection(polyLineSource.GetOutputPort())
    appendPolyData.Update()
    gridNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    gridNode.SetName("LineData")
    gridNode.SetAndObservePolyData(appendPolyData.GetOutputDataObject(0))
    gridNode.CreateDefaultDisplayNodes()
    groupArray = vtk.vtkFloatArray()
    groupArray.SetNumberOfTuples(lines*columns)
    groupArray.SetName("Group")
    pointData = gridNode.GetPolyData().GetPointData()
    pointData.AddArray(groupArray)
    groupNumpy = slicer.util.arrayFromModelPointData(gridNode, "Group")
    byLine = groupNumpy.reshape(lines,columns)
    for line in range(lines):
      byLine[line] = numpy.random.randint(groups)
    slicer.util.arrayFromModelPointDataModified(gridNode, "Group")
    displayNode = gridNode.GetDisplayNode()
    displayNode.SetOpacity(0.4)
    displayNode.SetLineWidth(4)
    displayNode.SetActiveScalarName("Group")
    displayNode.SetScalarVisibility(True)



    '''
    x = self.origin[0]
    startPoint = (x, 0, self.origin[1])
    endPoint = (x, 0, self.origin[1]+self.baseSize)

    modelsDM = slicer.app.layoutManager().threeDWidget(0).threeDView().displayableManagerByClassName('vtkMRMLModelDisplayableManager')
    actor = modelsDM.GetActorByID(gridNode.GetDisplayNode().GetID())
    mapper = actor.GetMapper()
    mapper.MapDataArrayToVertexAttribute(
        "textureCoordinates", "TextureCoordinates", vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS);
    shaderProperty = actor.GetShaderProperty()
    fragmentUniforms = shaderProperty.GetFragmentCustomUniforms()
    fragmentUniforms.SetUniformf("lineCount", 50)
    shaderProperty.ClearAllShaderReplacements()
    shaderProperty.AddVertexShaderReplacement(
          "//VTK::Light::Dec",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Dec
          in vec2 textureCoordinates;
          out vec2 interpolatedTextureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddVertexShaderReplacement(
          "//VTK::Light::Impl",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Impl
          interpolatedTextureCoordinates = textureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddFragmentShaderReplacement(
          "//VTK::TMap::Dec",  # replace the texture map block
          False,                 # after the standard replacements
          """
          //VTK::TMap::Dec
          in vec2 interpolatedTextureCoordinates;

          """,
          False # only do it once
    )
    shaderProperty.AddFragmentShaderReplacement(
          "//VTK::Light::Impl",  # replace the light block
          False,                 # after the standard replacements
          """
          //VTK::Light::Impl

          fragOutput0.rgb = vec3(0);

          float local = mod(interpolatedTextureCoordinates.x, 1./lineCount);
          fragOutput0.a = pow(1 - abs(0.5 - local), 2);
          fragOutput0.a = interpolatedTextureCoordinates.x / 1./lineCount;

          if (interpolatedTextureCoordinates.y < 0.5) {
            fragOutput0.a = mod(interpolatedTextureCoordinates.x, 1./lineCount);
          } else {
            local = fract(interpolatedTextureCoordinates.x * lineCount);
            fragOutput0.a = pow(1. - abs(0.5 - local),100);
          }

          fragOutput0.rgba = vec4(0,0,0,1);
          """,
          False # only do it once
    )
    slicer.modules.lineDataActor = actor
    '''

  def idcLineData(self, csvFilePath):
    data = {}
    fp = open(csvFilePath)
    csvReader = csv.DictReader(fp)
    for row in csvReader:
      data[row['SeriesInstanceUID']] = row
    slicer.modules.data = data
    return


    columnSize = self.baseSize / columns
    appendPolyData = vtk.vtkAppendPolyData()
    for line in range(lines):
      polyLineSource = vtk.vtkPolyLineSource()
      polyLineSource.SetNumberOfPoints(columns)
      value = random.random()
      for column in range(columns):
        line = vtk.vtkLineSource()
        offset = column * columnSize
        polyLineSource.SetPoint(column, self.origin[0]+offset, self.origin[1] + 1, self.origin[2] + value * self.baseSize)
        value += (random.random()-0.5) * .05
      appendPolyData.AddInputConnection(polyLineSource.GetOutputPort())
    appendPolyData.Update()
    gridNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    gridNode.SetName("LineData")
    gridNode.SetAndObservePolyData(appendPolyData.GetOutputDataObject(0))
    gridNode.CreateDefaultDisplayNodes()
    groupArray = vtk.vtkFloatArray()
    groupArray.SetNumberOfTuples(lines*columns)
    groupArray.SetName("Group")
    pointData = gridNode.GetPolyData().GetPointData()
    pointData.AddArray(groupArray)
    groupNumpy = slicer.util.arrayFromModelPointData(gridNode, "Group")
    byLine = groupNumpy.reshape(lines,columns)
    for line in range(lines):
      byLine[line] = numpy.random.randint(groups)
    slicer.util.arrayFromModelPointDataModified(gridNode, "Group")
    displayNode = gridNode.GetDisplayNode()
    displayNode.SetOpacity(0.4)
    displayNode.SetLineWidth(4)
    displayNode.SetActiveScalarName("Group")
    displayNode.SetScalarVisibility(True)

  def csvLineData(self, csvFilePath, columnSelection=None, groupSelect=None):
    fp = open(csvFilePath)
    dictReader = csv.DictReader(fp)
    columns = len(dictReader.fieldnames) if columnSelection is not None else len(columnSelection)
    columnSize = self.baseSize / columns
    groupSelect = groupSelect if groupSelect is not None else dictReader.fieldnames[0]
    appendPolyData = vtk.vtkAppendPolyData()
    lines = 0
    groupValues = []
    for row in dictReader:
      if row[groupSelect] not in groupValues:
        groupValues.append(row[groupSelect])
      polyLineSource = vtk.vtkPolyLineSource()
      polyLineSource.SetNumberOfPoints(columns)
      value = random.random()
      for column in range(columns):
        line = vtk.vtkLineSource()
        offset = column * columnSize
        polyLineSource.SetPoint(column, self.origin[0]+offset, self.origin[1] + 1, self.origin[2] + value * self.baseSize)
        value += (random.random()-0.5) * .05
      appendPolyData.AddInputConnection(polyLineSource.GetOutputPort())
      lines += 1
    appendPolyData.Update()

    gridNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    gridNode.SetName("LineData")
    gridNode.SetAndObservePolyData(appendPolyData.GetOutputDataObject(0))
    gridNode.CreateDefaultDisplayNodes()
    groupArray = vtk.vtkFloatArray()
    groupArray.SetNumberOfTuples(lines*columns)
    groupArray.SetName("Subject")
    pointData = gridNode.GetPolyData().GetPointData()
    pointData.AddArray(groupArray)
    groupNumpy = slicer.util.arrayFromModelPointData(gridNode, "Subject")
    byLine = groupNumpy.reshape(lines,columns)
    groups = len(groupValues)
    for line in range(lines):
      byLine[line] = numpy.random.randint(groups)
    slicer.util.arrayFromModelPointDataModified(gridNode, "Subject")
    displayNode = gridNode.GetDisplayNode()
    displayNode.SetOpacity(0.4)
    displayNode.SetLineWidth(4)
    displayNode.SetActiveScalarName("Subject")
    displayNode.SetScalarVisibility(True)

  def pandasLineData(self, csvFilePath, columnSelection=None):
    dataFrame = pandas.read_csv(csvFilePath, usecols=columnSelection, nrows=1000)

    slicer.modules.dataFrame = dataFrame

    columns = dataFrame.shape[1] if columnSelection is not None else len(columnSelection)
    columnSpacing = self.baseSize / columns
    valueRanges = {}
    for column in columnSelection:
      value = dataFrame[column][0]
      if not isinstance(value, str):
        valueRanges[column] = (dataFrame[column].min(), dataFrame[column].max())
      else:
        valueRanges[column] = (0, len(dataFrame.value_counts(column).keys().to_list())-1)
    appendPolyData = vtk.vtkAppendPolyData()
    lines = 0
    for rowIndex in range(dataFrame.shape[0]):
      polyLineSource = vtk.vtkPolyLineSource()
      polyLineSource.SetNumberOfPoints(columns)
      for columnIndex in range(len(columnSelection)):
        column = columnSelection[columnIndex]
        offset = columnIndex * columnSpacing
        valueRange = valueRanges[columnSelection[columnIndex]]
        value = dataFrame[column][rowIndex]
        if not isinstance(value, str):
          value = (value - valueRange[0]) / (valueRange[1] - valueRange[0])
        else:
          value = dataFrame.value_counts(column).keys().to_list().index(value) / valueRange[1]
        polyLineSource.SetPoint(columnIndex, self.origin[0]+self.baseSize - offset, self.origin[1] + 1, self.origin[2] + value * self.baseSize)
      appendPolyData.AddInputConnection(polyLineSource.GetOutputPort())
      lines += 1
    appendPolyData.Update()

    gridNode = slicer.mrmlScene.AddNode(slicer.vtkMRMLModelNode())
    gridNode.SetName("LineData")
    gridNode.SetAndObservePolyData(appendPolyData.GetOutputDataObject(0))
    gridNode.CreateDefaultDisplayNodes()
    groupArray = vtk.vtkFloatArray()
    groupArray.SetNumberOfTuples(lines*columns)
    groupArray.SetName("Subject")
    pointData = gridNode.GetPolyData().GetPointData()
    pointData.AddArray(groupArray)
    groupNumpy = slicer.util.arrayFromModelPointData(gridNode, "Subject")
    byLine = groupNumpy.reshape(lines,columns)
    for line in range(lines):
      byLine[line] = line
    slicer.util.arrayFromModelPointDataModified(gridNode, "Subject")
    displayNode = gridNode.GetDisplayNode()
    displayNode.SetOpacity(0.4)
    displayNode.SetLineWidth(1)
    displayNode.SetActiveScalarName("Subject")
    displayNode.SetScalarVisibility(True)
    viridisNode = slicer.util.getNode('Viridis')
    displayNode.SetAndObserveColorNodeID(viridisNode.GetID())

class GraphTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.y
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
    self.test_Graph1()

  def test_Graph1(self):
    """
    """

    self.messageDelay = 50
    self.delayDisplay("Starting the test")

    threeDView = slicer.app.layoutManager().threeDWidget(0).threeDView()
    threeDView.cameraNode().SetParallelProjection(False)
    threeDView.renderWindow().SetMultiSamples(16)
    viewNode = threeDView.mrmlViewNode()

    viewNode.SetBoxVisible(False)
    viewNode.SetAxisLabelsVisible(False)
    viewNode.SetBackgroundColor(0,0,0)
    viewNode.SetBackgroundColor2(0,0,0)

    logic = GraphLogic()
    slicer.modules.GraphWidget.logic = logic

    tagsToGraph = ['Modality', 'Study Description', 'Series Description', "Manufacturer's Model Name", 'Patient ID', "Patient's Sex", "Patient's Size", "Patient's Weight", 'Scan Options', 'Repetition Time', 'Echo Time', 'Trigger Time', 'Flip Angle', 'Diffusion b-value', 'Number of Frames', 'Rows', 'Columns', 'Pixel Spacing', "Patient's Age", 'Patient Comments', 'Modalities in Study', 'Institution Name', "Performing Physician's Name", "Referring Physician's Name", 'Body Part Examined', 'Contrast/Bolus Agent', 'Scanning Sequence', 'Echo Number(s)']

    if False:
      logic.markupsFromTags(tagsToGraph)

    if False:
      logic.lineGrid(columns=90)

    if False:
      logic.polyDataGrid(rows=10, columns=20)

    if False:
      logic.mipmapGrid(rows=10, columns=20)

    if False:
      logic.lineData(lines=100, columns=90)

    if False:
      slicer.modules.card = Card("<strong>About time</strong> we had cards again")

    if True:
      abcdFilePath = "/Users/pieper/data/ABCD/abcdRelease3_merged_DWI_withoutPhilips.csv" ;# for sliver
      abcdFilePath = "/opt/data/SlicerDMRI/NDA-ABCD-Tractology/abcdRelease3_merged_DWI_withoutPhilips.csv" ;# for hive

      columnSelection = ["src_subject_id", "device_id", "interview_age", "sex_x", "scrn_hr_school", "scrn_hr_disobey", "scrn_hr_sleep", "scrn_hr_fear", "scrn_hr_liecheat", "scrn_hr_music", "scrn_hr_dep", "scrn_hr_help", "scrn_hr_destroy", "scrn_hr_steal", "scrn_hr_sport", "scrn_hr_som", "scrn_hr_read", "scrn_hr_slowfriend", "scrn_hr_stress", "scrn_hr_smoke", "nihtbx_totalcomp_fc", "unhealthy"]

      columnSelection = ["src_subject_id", "device_id", "interview_age", "sex_x", "nihtbx_totalcomp_fc", "unhealthy"]

      logic.pandasLineData(abcdFilePath, columnSelection=columnSelection)

    """ Pandas Notes:

pip_install("pandas")
import pandas, numpy

df = pandas.read_csv("/Users/pieper/data/ABCD/abcdRelease3_merged_DWI_withoutPhilips.csv")

print(df.columns.values)

ppiq = df.pivot_table(index='scrn_hr_school', columns='sex_x', values="nihtbx_totalcomp_fc", aggfunc="mean")
print(ppiq)

list(df.sort_values('nihtbx_totalcomp_fc')['nihtbx_totalcomp_fc'])

df[df['nihtbx_totalcomp_fc'] < 20]['nihtbx_totalcomp_fc']

df.sum().loc['interview_age'] / df.count()[0]

df.loc[:,'interview_age'].sum() / df.count()[0] / 12

Device4


"""


    if False:
      csvFilePath = "/opt/data/idc/idc_v2-meta.csv"
      logic.idcLineData(csvFilePath=csvFilePath)

    if False:
      slicer.modules.page = Page("https://slicer.org")

    self.delayDisplay('Test passed!')
