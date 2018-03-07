# Copyright (C) 2017  DESY, Christoph Rosemann, Notkestr. 85, D-22607 Hamburg
#
# lavue is an image viewing program for photon science imaging detectors.
# Its usual application is as a live viewer using hidra as data source.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation in  version 2
# of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.
#
# Authors:
#     Jan Kotanski <jan.kotanski@desy.de>
#     Christoph Rosemann <christoph.rosemann@desy.de>
#

""" image widget """


from PyQt4 import QtCore, QtGui, uic

import os
import re
import math

from . import geometryDialog
from . import takeMotorsDialog
from . import motorWatchThread

_intensityformclass, _intensitybaseclass = uic.loadUiType(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "ui", "IntensityToolWidget.ui"))

_roiformclass, _roibaseclass = uic.loadUiType(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "ui", "ROIToolWidget.ui"))

_cutformclass, _cutbaseclass = uic.loadUiType(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "ui", "LineCutToolWidget.ui"))

_angleqformclass, _angleqbaseclass = uic.loadUiType(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "ui", "AngleQToolWidget.ui"))

_motorsformclass, _motorsbaseclass = uic.loadUiType(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "ui", "MotorsToolWidget.ui"))


class ToolParameters(object):
    """ tool parameters
    """
    def __init__(self):
        """ constructor

        """
        #: (:obj:`bool`) lines enabled
        self.lines = False
        #: (:obj:`bool`) rois enabled
        self.rois = False
        #: (:obj:`bool`) cuts enabled
        self.cuts = False
        #: (:obj:`bool`) axes scaling enabled
        self.scale = False
        #: (:obj:`bool`) cut plot enabled
        self.cutplot = False
        #: (:obj:`bool`) cross hair locker enabled
        self.crosshairlocker = False
        #: (:obj:`str`) infolineedit text
        self.infolineedit = None
        #: (:obj:`str`) infolabel text
        self.infolabel = None
        #: (:obj:`str`) infolabel text
        self.infotips = None


class ToolWidget(QtGui.QWidget):
    """ tool widget
    """
    def __init__(self, parent=None):
        """ constructor

        :param parent: parent object
        :type parent: :class:`PyQt4.QtCore.QObject`
        :param parameters: tool parameters
        :type parameters: :class:`ToolParameters`
        """
        QtGui.QWidget.__init__(self, parent)
        #: (:obj:`str`) tool name
        self.name = "None"
        #: (:class:`PyQt4.QtCore.QObject`) mainwidget
        self._mainwidget = parent
        #: (:class:`Ui_ToolWidget')
        #:     ui_toolwidget object from qtdesigner
        self._ui = None
        #: (:class:`ToolParameters`) tool parameters
        self.parameters = ToolParameters()

        #: (:obj:`list` < [:class:`PyQt4.QtCore.pyqtSignal`, :obj:`str`] >)
        #: list of [signal, slot] object to connect
        self.signal2slot = []


class IntensityToolWidget(ToolWidget):
    """ intensity tool widget
    """

    def __init__(self, parent=None):
        """ constructor

        :param parent: parent object
        :type parent: :class:`PyQt4.QtCore.QObject`
        """
        ToolWidget.__init__(self, parent)

        #: (:obj:`str`) tool name
        self.name = "Intensity"

        #: (:class:`Ui_IntensityToolWidget')
        #:        ui_toolwidget object from qtdesigner
        self.__ui = _intensityformclass()
        self.__ui.setupUi(self)

        #: (:obj:`bool`) lines enabled
        self.parameters.lines = True
        #: (:obj:`bool`) axes scaling enabled
        self.parameters.scale = True
        #: (:obj:`bool`) cross hair locker enabled
        self.parameters.crosshairlocker = True
        #: (:obj:`str`) infolineedit text
        self.parameters.infolineedit = ""
        #: (:obj:`str`) infolabel text
        self.parameters.infotips = \
            "coordinate info display for the mouse pointer"

        #: (:obj:`list` < [:class:`PyQt4.QtCore.pyqtSignal`, :obj:`str`] >)
        #: list of [signal, slot] object to connect
        self.signal2slot = [
            [self.__ui.axesPushButton.clicked, self._mainwidget.setTicks],
            [self._mainwidget.mouseImagePositionChanged, self._message]
        ]

    @QtCore.pyqtSlot()
    def _message(self):
        """ provides intensity message
        """
        x, y, intensity = self._mainwidget.currentIntensity()
        ilabel = self._mainwidget.scalingLabel()
        txdata, tydata = self._mainwidget.scaledxy(x, y)
        xunits, yunits = self._mainwidget.axesunits()
        if txdata is not None:
            message = "x = %f%s, y = %f%s, %s = %.2f" % (
                txdata,
                (" %s" % xunits) if xunits else "",
                tydata,
                (" %s" % yunits) if yunits else "",
                ilabel,
                intensity
            )
        else:
            message = "x = %i%s, y = %i%s, %s = %.2f" % (
                x,
                (" %s" % xunits) if xunits else "",
                y,
                (" %s" % yunits) if yunits else "",
                ilabel,
                intensity)
        self._mainwidget.setDisplayedText(message)


class MotorsToolWidget(ToolWidget):
    """ motors tool widget
    """

    def __init__(self, parent=None):
        """ constructor

        :param parent: parent object
        :type parent: :class:`PyQt4.QtCore.QObject`
        """
        ToolWidget.__init__(self, parent)

        #: (:obj:`str`) tool name
        self.name = "MoveMotors"

        #: (:obj:`str`) x-motor name
        self.__xmotorname = ""
        #: (:obj:`str`) y-motor name
        self.__ymotorname = ""
        #: (:obj:`str`) x final position
        self.__xfinal = None
        #: (:obj:`str`) y final position
        self.__yfinal = None
        #: (:class:`PyTango.DeviceProxy`) x-motor device
        self.__xmotordevice = None
        #: (:class:`PyTango.DeviceProxy`) y-motor device
        self.__ymotordevice = None
        #: (:class:`lavuelib.motorWatchThread.motorWatchThread`) motor watcher
        self.__motorWatcher = None

        #: (:class:`Ui_MotorsToolWidget')
        #:        ui_toolwidget object from qtdesigner
        self.__ui = _motorsformclass()
        self.__ui.setupUi(self)

        #: (:obj:`bool`) lines enabled
        self.parameters.lines = True
        #: (:obj:`bool`) cross hair locker enabled
        # self.parameters.crosshairlocker = True
        #: (:obj:`str`) infolineedit text
        self.parameters.infolineedit = ""
        #: (:obj:`str`) infolabel text
        self.parameters.infotips = \
            "coordinate info display for the mouse pointer"

        #: (:obj:`list` < [:class:`PyQt4.QtCore.pyqtSignal`, :obj:`str`] >)
        #: list of [signal, slot] object to connect
        self.signal2slot = [
            [self.__ui.takePushButton.clicked, self._setMotors],
            [self.__ui.movePushButton.clicked, self._moveStopMotors],
            [self._mainwidget.mouseImageDoubleClicked, self._updateFinal],
            [self._mainwidget.mouseImagePositionChanged, self._message]
        ]

    @QtCore.pyqtSlot(float, float)
    def _updateFinal(self, xdata, ydata):
        """ updates the final motors position

        :param xdata: x pixel position
        :type xdata: :obj:`float`
        :param ydata: y-pixel position
        :type ydata: :obj:`float`
        """
        self.__xfinal = float(xdata)
        self.__yfinal = float(ydata)
        self.__ui.xLineEdit.setText(str(self.__xfinal))
        self.__ui.yLineEdit.setText(str(self.__yfinal))
        self.__ui.movePushButton.setToolTip(
            "Move to x- and y-motors to (%s, %s)"
            % (self.__xfinal, self.__yfinal))

    @QtCore.pyqtSlot()
    def _moveStopMotors(self):
        if str(self.__ui.movePushButton.text()) == "Move":
            if self.__moveMotors():
                self.__ui.movePushButton.setText("Stop")
        else:
            if self.__stopMotors():
                self.__ui.movePushButton.setText("Move")

    @QtCore.pyqtSlot()
    def _finished(self):
        self.__stopMotors()

    def __stopMotors(self):
        """ move motors

        :returns: motors stopped
        :rtype: :obj:`bool`
        """
        try:
            if hasattr(self.__xmotordevice, "stop"):
                self.__xmotordevice.stop()
            elif hasattr(self.__xmotordevice, "StopMove"):
                self.__xmotordevice.StopMove()
            else:
                return False
            if hasattr(self.__ymotordevice, "stop"):
                self.__ymotordevice.stop()
            elif hasattr(self.__ymotordevice, "StopMove"):
                self.__ymotordevice.StopMove()
            else:
                return False
        except Exception as e:
            print(str(e))

        if self.__motorWatcher:
            self.__motorWatcher.motorStatusSignal.disconnect(self._showMotors)
            self.__motorWatcher.watchingFinished.disconnect(self._finished)
            self.__motorWatcher = None
        self.__ui.movePushButton.setText("Move")
        return True

    def __moveMotors(self):
        """ move motors

        :returns: motors started
        :rtype: :obj:`bool`
        """
        try:
            self.__xfinal = float(self.__ui.xLineEdit.text())
        except:
            self.__ui.xLineEdit.setFocus()
            return False
        try:
            self.__yfinal = float(self.__ui.yLineEdit.text())
        except:
            self.__ui.yLineEdit.setFocus()
            return False

        if self.__xmotordevice is None or self.__ymotordevice is None:
            if not self._setMotors():
                return False
        if str(self.__xmotordevice.state) != "ON" \
           and str(self.__ymotordevice.state) != "ON":
            try:
                self.__xmotordevice.position = self.__xfinal
                self.__ymotordevice.position = self.__yfinal
            except Exception as e:
                print(str(e))
                return False
        else:
            return False
        print("%s %s" % (self.__xfinal, self.__yfinal))
        self.__motorWatcher = motorWatchThread.MotorWatchThread(
            self.__xmotordevice, self.__ymotordevice)
        self.__motorWatcher.motorStatusSignal.connect(self._showMotors)
        self.__motorWatcher.watchingFinished.connect(self._finished)
        self.__motorWatcher.start()
        return True

    @QtCore.pyqtSlot(float, str, float, str)
    def _showMotors(self, position1, state1, position2, state2):
        """ shows motors positions and states
        """
        print("%s %s %s %s" % (position1, state1, position2, state2))

    @QtCore.pyqtSlot()
    def _setMotors(self):
        """ launches motors widget

        :returns: apply status
        :rtype: :obj:`bool`
        """
        cnfdlg = takeMotorsDialog.TakeMotorsDialog(self)
        cnfdlg.xmotorname = self.__xmotorname
        cnfdlg.ymotorname = self.__ymotorname
        cnfdlg.createGUI()
        if cnfdlg.exec_():
            self.__xmotorname = cnfdlg.xmotorname
            self.__ymotorname = cnfdlg.ymotorname
            self.__xmotordevice = cnfdlg.xmotordevice
            self.__ymotordevice = cnfdlg.ymotordevice
            self.__ui.takePushButton.setToolTip(
                "x-motor: %s\ny-motor: %s" % (
                    self.__xmotorname, self.__ymotorname))
            # self.updateGeometryTip()
            return True
        return False

    @QtCore.pyqtSlot()
    def _message(self):
        """ provides intensity message
        """
        x, y, intensity = self._mainwidget.currentIntensity()
        ilabel = self._mainwidget.scalingLabel()
        txdata, tydata = self._mainwidget.scaledxy(x, y)
        xunits, yunits = self._mainwidget.axesunits()
        if txdata is not None:
            message = "x = %f%s, y = %f%s, %s = %.2f" % (
                txdata,
                (" %s" % xunits) if xunits else "",
                tydata,
                (" %s" % yunits) if yunits else "",
                ilabel,
                intensity
            )
        else:
            message = "x = %i%s, y = %i%s, %s = %.2f" % (
                x,
                (" %s" % xunits) if xunits else "",
                y,
                (" %s" % yunits) if yunits else "",
                ilabel,
                intensity)
        self._mainwidget.setDisplayedText(message)


class ROIToolWidget(ToolWidget):
    """ roi tool widget
    """
    #: (:class:`PyQt4.QtCore.pyqtSignal`) apply ROI pressed signal
    applyROIPressed = QtCore.pyqtSignal(str, int)
    #: (:class:`PyQt4.QtCore.pyqtSignal`) fetch ROI pressed signal
    fetchROIPressed = QtCore.pyqtSignal(str)
    #: (:class:`PyQt4.QtCore.pyqtSignal`) roi info Changed signal
    roiInfoChanged = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        """ constructor

        :param parent: parent object
        :type parent: :class:`PyQt4.QtCore.QObject`
        """
        ToolWidget.__init__(self, parent)

        #: (:obj:`str`) tool name
        self.name = "ROI"

        #: (:class:`Ui_ROIToolWidget') ui_toolwidget object from qtdesigner
        self.__ui = _roiformclass()
        self.__ui.setupUi(self)

        self.parameters.rois = True
        self.parameters.infolineedit = ""
        self.parameters.infolabel = "[x1, y1, x2, y2], sum: "
        self.parameters.infotips = \
            "coordinate info display for the mouse pointer"
        self.__ui.applyROIPushButton.clicked.connect(self._emitApplyROIPressed)
        self.__ui.fetchROIPushButton.clicked.connect(self._emitFetchROIPressed)

        #: (:obj:`list` < [:class:`PyQt4.QtCore.pyqtSignal`, :obj:`str`] >)
        #: list of [signal, slot] object to connect
        self._updateApplyButton()
        self.signal2slot = [
            [self.applyROIPressed, self._mainwidget.applyROIs],
            [self.fetchROIPressed, self._mainwidget.fetchROIs],
            [self.roiInfoChanged, self._mainwidget.updateDisplayedText],
            [self.__ui.labelROILineEdit.textChanged,
             self._updateApplyButton],
            [self.__ui.roiSpinBox.valueChanged, self._mainwidget.updateROIs],
            [self._mainwidget.roiLineEditChanged, self._updateApplyButton],
            [self._mainwidget.roiAliasesChanged, self.updateROILineEdit],
            [self._mainwidget.roiValueChanged, self.updateROIDisplayText],
            [self._mainwidget.roiNumberChanged, self.setROIsNumber],
            [self._mainwidget.sardanaEnabled, self.updateROIButton],
            [self._mainwidget.mouseImagePositionChanged, self._message]
        ]

    @QtCore.pyqtSlot()
    def _message(self):
        """ provides roi message
        """
        message = ""
        current = self._mainwidget.currentROI()
        coords = self._mainwidget.roiCoords()
        if current > -1 and current < len(coords):
            message = "%s" % coords[current]
        self._mainwidget.setDisplayedText(message)

    @QtCore.pyqtSlot()
    def _emitApplyROIPressed(self):
        """ emits applyROIPressed signal"""

        text = str(self.__ui.labelROILineEdit.text())
        roispin = int(self.__ui.roiSpinBox.value())
        self.applyROIPressed.emit(text, roispin)

    @QtCore.pyqtSlot()
    def _emitFetchROIPressed(self):
        """ emits fetchROIPressed signal"""
        text = str(self.__ui.labelROILineEdit.text())
        self.fetchROIPressed.emit(text)

    @QtCore.pyqtSlot(str)
    @QtCore.pyqtSlot()
    def _updateApplyButton(self):
        """ updates applied button"""
        if not str(self.__ui.labelROILineEdit.text()).strip():
            self.__ui.applyROIPushButton.setEnabled(False)
        else:
            self.__ui.applyROIPushButton.setEnabled(True)

    @QtCore.pyqtSlot(str)
    def updateROILineEdit(self, text):
        """ updates ROI line edit text

        :param text: text to update
        :type text: :obj:`str`
        """
        self.__ui.labelROILineEdit.setText(text)
        self._updateApplyButton()

    @QtCore.pyqtSlot(bool)
    def updateROIButton(self, enabled):
        """ enables/disables ROI buttons

        :param enable: buttons enabled
        :type enable: :obj:`bool`
        """
        self.__ui.applyROIPushButton.setEnabled(enabled)
        self.__ui.fetchROIPushButton.setEnabled(enabled)

    @QtCore.pyqtSlot(int)
    def updateApplyTips(self, rid):
        """ updates apply tips

        :param rid: current roi id
        :type rid: :obj:`int`
        """
        if rid < 0:
            self.__ui.applyROIPushButton.setToolTip(
                "remove ROI aliases from the Door environment"
                " as well as from Active MntGrp")
        else:
            self.__ui.applyROIPushButton.setToolTip(
                "add ROI aliases to the Door environment "
                "as well as to Active MntGrp")

    @QtCore.pyqtSlot(str, int, str)
    def updateROIDisplayText(self, text, currentroi, roiVal):
        """ updates ROI display text

        :param text: standard display text
        :type text: :obj:`str`
        :param currentroi: current roi label
        :type currentroi: :obj:`str`
        :param text: roi sum value
        :type text: :obj:`str`
        """

        roilabel = "roi [%s]" % (currentroi + 1)
        slabel = []

        rlabel = str(self.__ui.labelROILineEdit.text())
        if rlabel:
            slabel = re.split(';|,| |\n', rlabel)
            slabel = [lb for lb in slabel if lb]
        if slabel:
            roilabel = "%s [%s]" % (
                slabel[currentroi]
                if currentroi < len(slabel) else slabel[-1],
                (currentroi + 1)
            )
        self.roiInfoChanged.emit("%s, %s = %s" % (text, roilabel, roiVal))

    @QtCore.pyqtSlot(int)
    def setROIsNumber(self, rid):
        """sets a number of rois

        :param rid: number of rois
        :type rid: :obj:`int`
        """
        self.__ui.roiSpinBox.setValue(rid)


class LineCutToolWidget(ToolWidget):
    """ line-cut tool widget
    """

    def __init__(self, parent=None):
        """ constructor

        :param parent: parent object
        :type parent: :class:`PyQt4.QtCore.QObject`
        """
        ToolWidget.__init__(self, parent)

        #: (:obj:`str`) tool name
        self.name = "LineCut"

        #: (:class:`Ui_LineCutToolWidget') ui_toolwidget object from qtdesigner
        self.__ui = _cutformclass()
        self.__ui.setupUi(self)

        self.parameters.cuts = True
        self.parameters.cutplot = True
        self.parameters.infolineedit = ""
        self.parameters.infotips = \
            "coordinate info display for the mouse pointer"

        #: (:obj:`list` < [:class:`PyQt4.QtCore.pyqtSignal`, :obj:`str`] >)
        #: list of [signal, slot] object to connect
        self.signal2slot = [
            [self.__ui.cutSpinBox.valueChanged, self._mainwidget.updateCuts],
            [self._mainwidget.cutNumberChanged, self._setCutsNumber],
            [self._mainwidget.mouseImagePositionChanged, self._message]
        ]

    @QtCore.pyqtSlot(int)
    def _setCutsNumber(self, cid):
        """sets a number of cuts

        :param cid: number of cuts
        :type cid: :obj:`int`
        """
        self.__ui.cutSpinBox.setValue(cid)

    @QtCore.pyqtSlot()
    def _message(self):
        """ provides cut message
        """
        x, y, intensity = self._mainwidget.currentIntensity()
        ilabel = self._mainwidget.scalingLabel()
        if self._mainwidget.currentCut() > -1:
            crds = self._mainwidget.cutCoords()[
                self._mainwidget.currentCut()]
            crds = "[[%.2f, %.2f], [%.2f, %.2f]]" % tuple(crds)
        else:
            crds = "[[0, 0], [0, 0]]"
        message = "%s, x = %i, y = %i, %s = %.2f" % (
            crds, x, y, ilabel, intensity)
        self._mainwidget.setDisplayedText(message)


class AngleQToolWidget(ToolWidget):
    """ angle/q tool widget
    """

    def __init__(self, parent=None):
        """ constructor

        :param parent: parent object
        :type parent: :class:`PyQt4.QtCore.QObject`
        """
        ToolWidget.__init__(self, parent)

        #: (:obj:`str`) tool name
        self.name = "Angle/Q"

        #: (:class:`Ui_ROIToolWidget') ui_toolwidget object from qtdesigner
        #: (:obj:`float`) x-coordinates of the center of the image
        self.__centerx = 0.0
        #: (:obj:`float`) y-coordinates of the center of the image
        self.__centery = 0.0
        #: (:obj:`float`) energy in eV
        self.__energy = 0.0
        #: (:obj:`float`) pixel x-size in um
        self.__pixelsizex = 0.0
        #: (:obj:`float`) pixel y-size in um
        self.__pixelsizey = 0.0
        #: (:obj:`float`) detector distance in mm
        self.__detdistance = 0.0
        #: (:obj:`int`) geometry space index -> 0: angle, 1 q-space
        self.__gspaceindex = 0

        self.__ui = _angleqformclass()
        self.__ui.setupUi(self)

        self.parameters.lines = True
        self.parameters.infolineedit = ""
        self.parameters.infotips = ""

        #: (:obj:`list` < [:class:`PyQt4.QtCore.pyqtSignal`, :obj:`str`] >)
        #: list of [signal, slot] object to connect
        self.signal2slot = [
            [self.__ui.angleqPushButton.clicked, self._setGeometry],
            [self.__ui.angleqComboBox.currentIndexChanged,
             self._setGSpaceIndex],
            [self._mainwidget.mouseImageDoubleClicked,
             self._updateCenter],
            [self._mainwidget.mouseImagePositionChanged, self._message]
        ]

    @QtCore.pyqtSlot(float, float)
    def _updateCenter(self, xdata, ydata):
        """ updates the image center

        :param xdata: x pixel position
        :type xdata: :obj:`float`
        :param ydata: y-pixel position
        :type ydata: :obj:`float`
        """
        self.__centerx = float(xdata)
        self.__centery = float(ydata)
        self._message()
        self.updateGeometryTip()

    @QtCore.pyqtSlot()
    def _message(self):
        """ provides geometry message
        """
        message = ""
        x, y, intensity = self._mainwidget.currentIntensity()
        ilabel = self._mainwidget.scalingLabel()
        if self.__gspaceindex == 0:
            thetax, thetay, thetatotal = self.__pixel2theta(x, y)
            if thetax is not None:
                message = "th_x = %f deg, th_y = %f deg," \
                          " th_tot = %f deg, %s = %.2f" \
                          % (thetax, thetay, thetatotal, ilabel, intensity)
        else:
            qx, qz, q = self.__pixel2q(x, y)
            if qx is not None:
                message = u"q_x = %f 1/\u212B, q_z = %f 1/\u212B, " \
                          u"q = %f 1/\u212B, %s = %.2f" \
                          % (qx, qz, q, ilabel, intensity)

        self._mainwidget.setDisplayedText(message)

    def __pixel2theta(self, xdata, ydata):
        """ converts coordinates from pixel positions to theta angles

        :param xdata: x pixel position
        :type xdata: :obj:`float`
        :param ydata: y-pixel position
        :type ydata: :obj:`float`
        :returns: x-theta, y-theta, total-theta
        :rtype: (:obj:`float`, :obj:`float`, :obj:`float`)
        """
        thetax = None
        thetay = None
        thetatotal = None
        if self.__energy > 0 and self.__detdistance > 0:
            xcentered = xdata - self.__centerx
            ycentered = ydata - self.__centery
            thetax = math.atan(
                xcentered * self.__pixelsizex/1000. / self.__detdistance)
            thetay = math.atan(
                ycentered * self.__pixelsizey/1000. / self.__detdistance)
            r = math.sqrt((xcentered * self.__pixelsizex / 1000.) ** 2
                          + (ycentered * self.__pixelsizex / 1000.) ** 2)
            thetatotal = math.atan(r/self.__detdistance)*180/math.pi
        return thetax, thetay, thetatotal

    def __pixel2q(self, xdata, ydata):
        """ converts coordinates from pixel positions to q-space coordinates

        :param xdata: x pixel position
        :type xdata: :obj:`float`
        :param ydata: y-pixel position
        :type ydata: :obj:`float`
        :returns: q_x, q_y, q_total
        :rtype: (:obj:`float`, :obj:`float`, :obj:`float`)
        """
        qx = None
        qz = None
        q = None
        if self.__energy > 0 and self.__detdistance > 0:
            thetax, thetay, thetatotal = self.__pixel2theta(
                xdata, ydata)
            wavelength = 12400./self.__energy
            qx = 4 * math.pi / wavelength * math.sin(thetax/2.)
            qz = 4 * math.pi / wavelength * math.sin(thetay/2.)
            q = 4 * math.pi / wavelength * math.sin(thetatotal/2.)
        return qx, qz, q

    def __tipmessage(self):
        """ provides geometry messate

        :returns: geometry text
        :rtype: :obj:`unicode`
        """

        return u"geometry:\n" \
            u"  center = (%s, %s) pixels\n" \
            u"  pixel_size = (%s, %s) \u00B5m\n" \
            u"  detector_distance = %s mm\n" \
            u"  energy = %s eV" % (
                self.__centerx,
                self.__centery,
                self.__pixelsizex,
                self.__pixelsizey,
                self.__detdistance,
                self.__energy
            )

    @QtCore.pyqtSlot()
    def _setGeometry(self):
        """ launches geometry widget

        :returns: apply status
        :rtype: :obj:`bool`
        """
        cnfdlg = geometryDialog.GeometryDialog(self)
        cnfdlg.centerx = self.__centerx
        cnfdlg.centery = self.__centery
        cnfdlg.energy = self.__energy
        cnfdlg.pixelsizex = self.__pixelsizex
        cnfdlg.pixelsizey = self.__pixelsizey
        cnfdlg.detdistance = self.__detdistance
        cnfdlg.createGUI()
        if cnfdlg.exec_():
            self.__centerx = cnfdlg.centerx
            self.__centery = cnfdlg.centery
            self.__energy = cnfdlg.energy
            self.__pixelsizex = cnfdlg.pixelsizex
            self.__pixelsizey = cnfdlg.pixelsizey
            self.__detdistance = cnfdlg.detdistance
            self.updateGeometryTip()

    @QtCore.pyqtSlot(int)
    def _setGSpaceIndex(self, gindex):
        """ set gspace index

        :param gspace: g-space index, i.e. angle or q-space
        :type gspace: :obj:`int`
        """
        self.__gspaceindex = gindex

    def updateGeometryTip(self):
        """ update geometry tips
        """
        message = self.__tipmessage()
        self._mainwidget.updateDisplayedTextTip(
            "coordinate info display for the mouse pointer\n%s"
            % message)
        self.__ui.angleqPushButton.setToolTip(
            "Input physical parameters\n%s" % message)
        self.__ui.angleqComboBox.setToolTip(
            "Select the display space\n%s" % message)
        self.__ui.toolLabel.setToolTip(
            "coordinate info display for the mouse pointer\n%s" % message)
