"""
BORIS
Behavioral Observation Research Interactive Software
Copyright 2012-2021 Olivier Friard


  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
  MA 02110-1301, USA.

"""

import wave

import matplotlib
matplotlib.use("Qt5Agg")
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal, QEvent
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import parselmouth

class Plot_spectrogram_RT(QWidget):

    # send keypress event to mainwindow
    sendEvent = pyqtSignal(QEvent)

    def get_wav_info(self, wav_file: str):
        """
        read wav file and extract information
        """
        try:
            wav = wave.open(wav_file, "r")
            frames = wav.readframes(-1)
            sound_info = np.fromstring(frames, dtype=np.int16)
            frame_rate = wav.getframerate()
            wav.close()
            return sound_info, frame_rate
        except Exception:
            return np.array([]), 0


    def __init__(self):
        super().__init__()

        self.interval = 10  # interval of visualization (in seconds)
        self.time_mem = -1

        self.cursor_color = "red"

        self.spectro_color_map = matplotlib.pyplot.get_cmap("viridis")

        self.figure = Figure()

        self.canvas = FigureCanvas(self.figure)
        #self.canvas.clicked.connect(self.canvas_clicked)

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)

        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(QLabel("Time interval"))
        button_time_inc = QPushButton("+", self)
        button_time_inc.clicked.connect(lambda: self.time_interval_changed(1))
        button_time_dec = QPushButton("-", self)
        button_time_dec.clicked.connect(lambda: self.time_interval_changed(-1))
        hlayout1.addWidget(button_time_inc)
        hlayout1.addWidget(button_time_dec)
        layout.addLayout(hlayout1)

        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(QLabel("Frequency interval"))
        self.sb_freq_min = QSpinBox()
        self.sb_freq_min.setRange(0, 200000)
        self.sb_freq_min.setSingleStep(100)
        self.sb_freq_min.valueChanged.connect(self.frequency_interval_changed)
        self.sb_freq_max = QSpinBox()
        self.sb_freq_max.setRange(0, 200000)
        self.sb_freq_max.setSingleStep(100)
        self.sb_freq_max.valueChanged.connect(self.frequency_interval_changed)
        hlayout2.addWidget(self.sb_freq_min)
        hlayout2.addWidget(self.sb_freq_max)
        layout.addLayout(hlayout2)

        self.setLayout(layout)

        self.installEventFilter(self)

    def canvas_clicked(self):
        print("canvas clicked")


    def eventFilter(self, receiver, event):
        """
        send event (if keypress) to main window
        """
        if(event.type() == QEvent.KeyPress):
            self.sendEvent.emit(event)
            return True
        else:
            return False


    def time_interval_changed(self, action: int):
        """
        change the time interval for plotting spectrogram

        Args:
            action (int): -1 decrease time interval, +1 increase time interval
        """
        if action == -1 and self.interval <= 5:
            return
        self.interval += (5 * action)
        self.plot_spectro(current_time=self.time_mem, force_plot=True)


    def frequency_interval_changed(self):
        """
        change the frequency interval for plotting spectrogram
        """
        self.plot_spectro(current_time=self.time_mem, force_plot=True)


    def load_wav(self, wav_file_path: str) -> dict:
        """
        load wav file in numpy array

        Args:
            wav_file_path (str): path of wav file

        Returns:
            dict: "error" key if error, "media_length" and "frame_rate"
        """

        try:
            self.sound_info, self.frame_rate = self.get_wav_info(wav_file_path)
            if not self.frame_rate:
                return {"error": f"unknown format for file {wav_file_path}"}
        except FileNotFoundError:
            return {"error": f"File not found: {wav_file_path}"}

        self.media_length = len(self.sound_info) / self.frame_rate

        self.wav_file_path = wav_file_path

        self.snd = parselmouth.Sound(wav_file_path)

        pre_emphasized_snd = self.snd.copy()
        pre_emphasized_snd.pre_emphasize()
        self.spectrogram = pre_emphasized_snd.to_spectrogram()

        #self.spectrogram = self.snd.to_spectrogram()
        self.X, self.Y = self.spectrogram.x_grid(), self.spectrogram.y_grid()
        self.sg_db = 10 * np.log10(self.spectrogram.values)
        self.spectrogram_ymin, self.spectrogram_ymax = self.spectrogram.ymin, self.spectrogram.ymax


        dynamic_range = 70
        self.ax = self.figure.add_subplot(1, 1, 1)
        self.ax.pcolormesh(self.X, self.Y, self.sg_db,
                           vmin=self.sg_db.max() - dynamic_range,
                           cmap=self.spectro_color_map,
                           picker=5)
        self.ax.set_ylim(self.spectrogram_ymin, self.spectrogram_ymax)

        self.cursor = None

        return {"media_length": self.media_length,
                "frame_rate": self.frame_rate}


    def onpick(self, event):

        print("clicked")
        return True

        '''
        if event.artist!=line: return True

        N = len(event.ind)
        if not N: return True


        figi = plt.figure()
        for subplotnum, dataind in enumerate(event.ind):
            ax = figi.add_subplot(N,1,subplotnum+1)
            ax.plot(X[dataind])
            ax.text(0.05, 0.9, 'mu=%1.3f\nsigma=%1.3f'%(xs[dataind], ys[dataind]),
                    transform=ax.transAxes, va='top')
            ax.set_ylim(-0.5, 1.5)
        figi.show()
        return True
        '''



    def plot_spectro(self, current_time: float, force_plot: bool=False):
        """
        plot sound spectrogram centered on the current time

        Args:
            current_time (float): time for displaying spectrogram
        """

        if not force_plot and current_time == self.time_mem:
            return

        # self.time_mem = current_time

        self.ax.set_xlim(current_time - self.interval / 2, current_time + self.interval / 2)

        if self.cursor is not None:  #  https://stackoverflow.com/questions/13661366/clear-only-part-of-matplotlib-figure
            self.cursor.remove()
            del self.cursor

        self.cursor = self.ax.axvline(x=current_time, color=self.cursor_color, linestyle="-")

        #self.figure.subplots_adjust(wspace=0, hspace=0)

        self.canvas.draw()

        self.canvas.mpl_connect('pick_event', self.onpick)  # https://stackoverflow.com/questions/43114508/can-a-pyqt-embedded-matplotlib-graph-be-interactive

        return


