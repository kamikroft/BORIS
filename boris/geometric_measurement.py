"""
BORIS
Behavioral Observation Research Interactive Software
Copyright 2012-2022 Olivier Friard

This file is part of BORIS.

  BORIS is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 3 of the License, or
  any later version.

  BORIS is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not see <http://www.gnu.org/licenses/>.

"""

import logging
from . import menu_options
from . import utilities as util

from PyQt5.QtCore import pyqtSignal, Qt, QPoint
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QRadioButton,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QCheckBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from . import dialog
from . import config as cfg


class wgMeasurement(QWidget):
    """ """

    closeSignal, clearSignal = pyqtSignal(), pyqtSignal()
    flagSaved = True
    draw_mem = []

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Geometric measurements")

        vbox = QVBoxLayout(self)

        self.rbPoint = QRadioButton("Point (left click)")
        vbox.addWidget(self.rbPoint)

        self.rbDistance = QRadioButton("Distance (start: left click, end: right click)")
        vbox.addWidget(self.rbDistance)

        self.rbArea = QRadioButton("Area (left click for area vertices, right click to close area)")
        vbox.addWidget(self.rbArea)

        self.rbAngle = QRadioButton("Angle (vertex: left click, segments: right click)")
        vbox.addWidget(self.rbAngle)

        self.cbPersistentMeasurements = QCheckBox("Measurements are persistent")
        self.cbPersistentMeasurements.setChecked(True)
        vbox.addWidget(self.cbPersistentMeasurements)

        vbox.addWidget(QLabel("<b>Scale</b>"))

        hbox1 = QHBoxLayout()

        self.lbRef = QLabel("Reference")
        hbox1.addWidget(self.lbRef)

        self.lbPx = QLabel("Pixels")
        hbox1.addWidget(self.lbPx)

        vbox.addLayout(hbox1)

        hbox2 = QHBoxLayout()

        self.leRef = QLineEdit()
        self.leRef.setText("1")
        hbox2.addWidget(self.leRef)

        self.lePx = QLineEdit()
        self.lePx.setText("1")
        hbox2.addWidget(self.lePx)

        vbox.addLayout(hbox2)

        self.pte = QPlainTextEdit()
        vbox.addWidget(self.pte)

        self.status_lb = QLabel()
        vbox.addWidget(self.status_lb)

        hbox3 = QHBoxLayout()

        self.pbClear = QPushButton("Clear measurements", clicked=self.pbClear_clicked)
        hbox3.addWidget(self.pbClear)

        self.pbSave = QPushButton("Save results", clicked=self.pbSave_clicked)
        hbox3.addWidget(self.pbSave)

        self.pbClose = QPushButton("Close", clicked=self.pbClose_clicked)
        hbox3.addWidget(self.pbClose)

        vbox.addLayout(hbox3)

    def closeEvent(self, event):

        print("close event")
        self.pbClose_clicked()

    def pbClear_clicked(self):
        """
        clear measurements draw and results
        """
        self.draw_mem = {}
        self.pte.clear()
        self.clearSignal.emit()

    def pbClose_clicked(self):

        print("pb close clicked")
        if not self.flagSaved:
            response = dialog.MessageDialog(
                cfg.programName,
                "The current measurements are not saved. Do you want to save results before closing?",
                [cfg.YES, cfg.NO, cfg.CANCEL],
            )
            if response == cfg.YES:
                self.pbSave_clicked()
            if response == cfg.CANCEL:
                return
        self.closeSignal.emit()

    def pbSave_clicked(self):
        """
        save results
        """
        if self.pte.toPlainText():
            fileName, _ = QFileDialog().getSaveFileName(
                self, "Save geometric measurements", "", "Text files (*.txt);;All files (*)"
            )
            if fileName:
                try:
                    with open(fileName, "w") as f:
                        f.write(self.pte.toPlainText())
                    self.flagSaved = True
                except Exception:
                    QMessageBox.warning(self, cfg.programName, "An error occured during saving the measurements")
        else:
            QMessageBox.information(self, cfg.programName, "There are no measurements to save")


def show_widget(self):
    """
    active the geometric measurement widget
    """

    def close_measurement_widget():

        self.geometric_measurements_mode = False
        for n_player, dw in enumerate(self.dw_player):
            dw.frame_viewer.clear()
            dw.stack.setCurrentIndex(0)
            dw.setWindowTitle(f"Player #{n_player + 1}")
        self.measurement_w.close()

        menu_options.update_menu(self)

        self.actionPlay.setEnabled(True)

    self.geometric_measurements_mode = True
    self.pause_video()

    menu_options.update_menu(self)

    self.actionPlay.setEnabled(False)

    self.measurement_w = wgMeasurement()
    self.measurement_w.draw_mem = {}
    self.measurement_w.setWindowFlags(Qt.WindowStaysOnTopHint)
    self.measurement_w.closeSignal.connect(close_measurement_widget)
    self.measurement_w.show()

    for _, dw in enumerate(self.dw_player):
        dw.setWindowTitle("Geometric measurements")
        dw.stack.setCurrentIndex(1)
        self.extract_frame(dw)


def draw_point(self, x, y, color, n_player=0):
    """
    draw point on frame-by-frame image
    """
    RADIUS = 6
    painter = QPainter()
    painter.begin(self.dw_player[n_player].frame_viewer.pixmap())
    painter.setPen(QColor(color))
    painter.drawEllipse(QPoint(x, y), RADIUS, RADIUS)
    # cross inside circle
    painter.drawLine(x - RADIUS, y, x + RADIUS, y)
    painter.drawLine(x, y - RADIUS, x, y + RADIUS)
    painter.end()
    self.dw_player[n_player].frame_viewer.update()


def draw_line(self, x1, y1, x2, y2, color, n_player=0):
    """
    draw line on frame-by-frame image
    """
    painter = QPainter()
    painter.begin(self.dw_player[n_player].frame_viewer.pixmap())
    painter.setPen(QColor(color))
    painter.drawLine(x1, y1, x2, y2)
    painter.end()
    self.dw_player[n_player].frame_viewer.update()


def image_clicked(self, n_player, event):
    """
    Geometric measurements on image

    Args:
        n_player (int): id of clicked player
        event (Qevent): event (mousepressed)
    """

    logging.debug(f"function image_clicked")

    if self.mem_player != -1 and n_player != self.mem_player:
        self.mem_player = n_player
        return

    self.mem_player = n_player
    current_frame = self.dw_player[n_player].player.estimated_frame_number
    if hasattr(self, "measurement_w") and self.measurement_w is not None and self.measurement_w.isVisible():
        x, y = event.pos().x(), event.pos().y()

        # convert label coordinates in pixmap coordinates
        x = int(
            x
            - (self.dw_player[n_player].frame_viewer.width() - self.dw_player[n_player].frame_viewer.pixmap().width())
            / 2
        )
        y = int(
            y
            - (self.dw_player[n_player].frame_viewer.height() - self.dw_player[n_player].frame_viewer.pixmap().height())
            / 2
        )

        # convert pixmap coordinates in video coordinates
        x_video = round(
            (x / self.dw_player[n_player].frame_viewer.pixmap().width()) * self.dw_player[n_player].player.width
        )
        y_video = round(
            (y / self.dw_player[n_player].frame_viewer.pixmap().height()) * self.dw_player[n_player].player.height
        )

        if not (
            0 <= x <= self.dw_player[n_player].frame_viewer.pixmap().width()
            and 0 <= y <= self.dw_player[n_player].frame_viewer.pixmap().height()
        ):
            self.measurement_w.status_lb.setText("<b>The click is outside the video area!</b>")
            return

        self.measurement_w.status_lb.clear()

        # point
        if self.measurement_w.rbPoint.isChecked():
            if event.button() == 1:  # left
                draw_point(self, x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player)
                if current_frame in self.measurement_w.draw_mem:
                    self.measurement_w.draw_mem[current_frame].append([n_player, "point", x, y])
                else:
                    self.measurement_w.draw_mem[current_frame] = [[n_player, "point", x, y]]

                self.measurement_w.pte.appendPlainText(
                    (
                        f"Time: {self.getLaps():.3f}\tPlayer: {n_player + 1}\t"
                        f"Frame: {current_frame}\tPoint: {x_video},{y_video}"
                    )
                )

        # distance
        elif self.measurement_w.rbDistance.isChecked():
            if event.button() == 1:  # left
                cfg.geometric_measurement.draw_point(self, x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player)
                self.memx, self.memy = x, y
                self.memx_video, self.memy_video = x_video, y_video

            if event.button() == 2 and self.memx != -1 and self.memy != -1:
                draw_point(self, x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player)
                draw_line(self, self.memx, self.memy, x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player)

                if current_frame in self.measurement_w.draw_mem:
                    self.measurement_w.draw_mem[current_frame].append([n_player, "line", self.memx, self.memy, x, y])
                else:
                    self.measurement_w.draw_mem[current_frame] = [[n_player, "line", self.memx, self.memy, x, y]]

                distance = ((x_video - self.memx_video) ** 2 + (y_video - self.memy_video) ** 2) ** 0.5
                try:
                    distance = distance / float(self.measurement_w.lePx.text()) * float(self.measurement_w.leRef.text())
                except Exception:
                    QMessageBox.critical(
                        None,
                        cfg.programName,
                        "Check reference and pixel values! Values must be numeric.",
                        QMessageBox.Ok | QMessageBox.Default,
                        QMessageBox.NoButton,
                    )

                self.measurement_w.pte.appendPlainText(
                    (
                        f"Time: {self.getLaps()}\tPlayer: {n_player + 1}\t"
                        f"Frame: {current_frame}\tDistance: {round(distance, 1)}"
                    )
                )
                self.measurement_w.flagSaved = False
                self.memx, self.memy = -1, -1

        # angle 1st clic -> vertex
        elif self.measurement_w.rbAngle.isChecked():
            if event.button() == 1:  # left for vertex
                draw_point(self, x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player)
                self.memPoints = [(x, y)]

            if event.button() == 2 and len(self.memPoints):
                draw_point(self, x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player)
                draw_line(
                    self, self.memPoints[0][0], self.memPoints[0][1], x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player
                )

                self.memPoints.append((x, y))

                if len(self.memPoints) == 3:
                    self.measurement_w.pte.appendPlainText(
                        (
                            f"Time: {self.getLaps()}\tPlayer: {n_player + 1}\t"
                            f"Frame: {current_frame}\t"
                            f"Angle: {round(util.angle(self.memPoints[0], self.memPoints[1], self.memPoints[2]), 1)}"
                        )
                    )
                    self.measurement_w.flagSaved = False
                    if current_frame in self.measurement_w.draw_mem:
                        self.measurement_w.draw_mem[current_frame].append([n_player, "angle", self.memPoints])
                    else:
                        self.measurement_w.draw_mem[current_frame] = [[n_player, "angle", self.memPoints]]

                    self.memPoints = []

        # Area
        elif self.measurement_w.rbArea.isChecked():
            if event.button() == 1:  # left
                draw_point(self, x, y, cfg.ACTIVE_MEASUREMENTS_COLOR)
                if len(self.memPoints):
                    draw_line(
                        self.memPoints[-1][0], self.memPoints[-1][1], x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player
                    )
                self.memPoints.append((x, y))
                self.memPoints_video.append((x_video, y_video))

            if event.button() == 2 and len(self.memPoints) >= 2:
                draw_point(self, x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player)
                draw_line(
                    self, self.memPoints[-1][0], self.memPoints[-1][1], x, y, cfg.ACTIVE_MEASUREMENTS_COLOR, n_player
                )
                self.memPoints.append((x, y))
                self.memPoints_video.append((x_video, y_video))

                # close polygon
                draw_line(
                    self,
                    self.memPoints[-1][0],
                    self.memPoints[-1][1],
                    self.memPoints[0][0],
                    self.memPoints[0][1],
                    cfg.ACTIVE_MEASUREMENTS_COLOR,
                    n_player,
                )
                area = util.polygon_area(self.memPoints_video)

                if current_frame in self.measurement_w.draw_mem:
                    self.measurement_w.draw_mem[current_frame].append([n_player, "polygon", self.memPoints])
                else:
                    self.measurement_w.draw_mem[current_frame] = [[n_player, "polygon", self.memPoints]]
                try:
                    area = (
                        area
                        / (float(self.measurement_w.lePx.text()) ** 2)
                        * float(self.measurement_w.leRef.text()) ** 2
                    )
                except Exception:
                    QMessageBox.critical(
                        None,
                        cfg.programName,
                        "Check reference and pixel values! Values must be numeric.",
                        QMessageBox.Ok | QMessageBox.Default,
                        QMessageBox.NoButton,
                    )

                self.measurement_w.pte.appendPlainText(
                    (
                        f"Time: {self.getLaps()}\tPlayer: {n_player + 1}\t"
                        f"Frame: {current_frame}\tArea: {round(area, 1)}"
                    )
                )
                self.memPoints, self.memPoints_video = [], []

        else:
            self.measurement_w.status_lb.setText("<b>Choose a measurement type!</b>")

    else:  # no measurements
        QMessageBox.warning(
            self,
            cfg.programName,
            "The Focus area function is not yet available in frame-by-frame mode.",
            QMessageBox.Ok | QMessageBox.Default,
            QMessageBox.NoButton,
        )


if __name__ == "__main__":

    import sys

    app = QApplication(sys.argv)
    w = wgMeasurement(logging.getLogger().getEffectiveLevel())
    w.show()

    sys.exit(app.exec_())
