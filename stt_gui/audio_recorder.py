#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
Module for a dialog window that allows users to record audio.
"""


import ctypes
#
import numpy as np
from PySide2 import QtCore, QtWidgets, QtMultimedia
#
from .dialogs import InfoDialog
from .utils import seconds_to_timestamp
from .widgets import DecimalSlider


# #############################################################################
# ## AUDIO RECORDER
# #############################################################################
class AudioRecorderDialog(QtWidgets.QDialog):
    """
    This class corresponds to a Qt dialog window with buttons to select
    recording device, information about the ongoing recording, and buttons to
    start/stop/save the recording.

    Each time an audio frame arrives to ``on_audio_probe``, it is appended to
    the ``self.result`` list. Once we are done with the dialog, we can e.g.
    concatenate the frames to store the recording, compute their energies to
    feed an audio meter...

    Modified from::
      https://doc.qt.io/qt-5/qtmultimedia-multimedia-audiorecorder-example.html
    """
    WINDOW_TITLE = "Record Sound"
    REC_BUTTON_TEXT = "Record"
    PAUSE_BUTTON_TEXT = "Pause"
    ACCEPT_BUTTON_TEXT = "Accept"
    NUM_DECIMALS_LABEL = 2  # How many decimals are displayed on label

    @classmethod
    def record_audio(cls, parent=None, max_allowed_secs=600):
        """
        """
        dialog = cls(parent, max_allowed_secs)
        was_accepted = bool(dialog.exec_())
        if was_accepted:
            return dialog.result, dialog.sample_rate
        else:
            return [], None

    def __init__(self, parent=None, max_allowed_secs=600):
        """
        """
        super().__init__(parent)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.max_allowed_secs = max_allowed_secs
        #
        self.audio_recorder = QtMultimedia.QAudioRecorder(self)
        self.audio_recorder.durationChanged.connect(self.on_duration_changed)
        self.audio_recorder.statusChanged.connect(self.on_status_changed)
        # self.audio_recorder.stateChanged.connect(self.on_state_changed)
        #
        self.audio_probe = QtMultimedia.QAudioProbe(self)
        self.audio_probe.setSource(self.audio_recorder)
        self.audio_probe.audioBufferProbed.connect(self.on_audio_probe)
        #
        self._setup_gui()
        #
        self.vol_s.setValue(100)
        self.result = []
        self.sample_rate = -1

    def _setup_body(self, lyt):
        """
        """
        self.form = QtWidgets.QFormLayout()
        lyt.addLayout(self.form)
        #
        # audio devices
        self.devices_cbox = QtWidgets.QComboBox()
        self.devices_cbox.addItems(self.audio_recorder.audioInputs())
        self.form.addRow("Input Device:", self.devices_cbox)
        self.devices_cbox.currentTextChanged.connect(
            lambda txt: self.audio_recorder.setAudioInput(txt))
        # audio codecs
        self.codecs_cbox = QtWidgets.QComboBox()
        self.codecs_cbox.addItems(self.audio_recorder.supportedAudioCodecs())
        self.form.addRow("Audio Codec:", self.codecs_cbox)
        # (ignored sample rate and containers)
        # volume
        self.vol_s = DecimalSlider(0, 1, 3, QtCore.Qt.Horizontal)
        self.form.addRow("Volume:", self.vol_s)
        self.vol_s.decimalValueChanged.connect(
            lambda vol: self.audio_recorder.setVolume(vol))
        # Duration display
        self.dur_l = QtWidgets.QLabel(
            seconds_to_timestamp(0, self.NUM_DECIMALS_LABEL))
        self.form.addRow("Recording Duration:", self.dur_l)

    def _setup_gui(self):
        """
        """
        #
        self.main_layout = QtWidgets.QVBoxLayout(self)
        # body layout
        self.body_layout = QtWidgets.QVBoxLayout()
        self._setup_body(self.body_layout)
        self.main_layout.addLayout(self.body_layout)
        # button layout
        self.button_layout = QtWidgets.QHBoxLayout()
        #
        self.rec_b = QtWidgets.QPushButton(self.REC_BUTTON_TEXT)
        self.button_layout.addWidget(self.rec_b)
        self.rec_b.clicked.connect(self.on_toggle_rec)
        self.rec_b.setAutoDefault(True)
        #
        self.accept_b = QtWidgets.QPushButton(self.ACCEPT_BUTTON_TEXT)
        self.button_layout.addWidget(self.accept_b)
        self.accept_b.clicked.connect(self.accept)
        self.accepted.connect(self.on_accept)
        #
        self.main_layout.addLayout(self.button_layout)

    def on_duration_changed(self, dur):
        """
        """
        dur_secs = dur / 1000.0
        pos_txt = seconds_to_timestamp(dur_secs, self.NUM_DECIMALS_LABEL)
        self.dur_l.setText(pos_txt)
        if dur_secs > self.max_allowed_secs:
            self.audio_recorder.pause()
            msg = (f"Max allowed recording time ({self.max_allowed_secs}) " +
                   "was surpassed and recording stopped. Save recording?")
            dialog = InfoDialog("Maximal allowed rec time surpassed",
                                msg, accept_button_name="YES, save",
                                reject_button_name="NO, don't save",
                                print_msg=False, parent=self)
            user_wants_save = bool(dialog.exec_())
            if user_wants_save:
                self.accept_b.click()
            else:
                self.reject()

    def on_status_changed(self, status):
        """
        """
        if status == self.audio_recorder.RecordingStatus:
            self.rec_b.setText(self.PAUSE_BUTTON_TEXT)
        else:
            self.rec_b.setText(self.REC_BUTTON_TEXT)

    def on_accept(self):
        """
        """
        self.audio_recorder.stop()  # stop automatically saves to disk!
        final_duration = self.audio_recorder.duration()

    def on_toggle_rec(self):
        """
        """
        status = self.audio_recorder.status()
        if status == self.audio_recorder.RecordingStatus:
            self.audio_recorder.pause()
        else:
            self.audio_recorder.record()

    @staticmethod
    def get_buffer_info(buf):
        """
        """
        num_bytes = buf.byteCount()
        num_frames = buf.frameCount()
        #
        fmt = buf.format()
        sample_type = fmt.sampleType()  # float, int, uint
        bytes_per_frame = fmt.bytesPerFrame()
        sample_rate = fmt.sampleRate()
        #
        if sample_type == fmt.Float and bytes_per_frame == 2:
            dtype = np.float32
            ctype = ctypes.c_float
        elif sample_type == fmt.SignedInt and bytes_per_frame == 2:
            dtype = np.int16
            ctype = ctypes.c_int16
        elif sample_type == fmt.UnsignedInt and bytes_per_frame == 2:
            dtype = np.uint16
            ctype = ctypes.c_uint16
        #
        return dtype, ctype, num_bytes, num_frames, bytes_per_frame, sample_rate

    def on_audio_probe(self, audio_buffer):
        """
        """
        # PLEASE NOTE:
        # there is a known issue with the Python interface, by which
        # on_audio_probe retrieves apparently empty buffers. See:
        # https://stackoverflow.com/a/67483225 and update this implementation
        # when the Qt bug has been fixed.
        # This implementation reads the array pointer idx, infers the length
        # and datatype, and assumes that the correct buffer will be found there.
        # This bypasses the Python garbage collector as well as other library
        # layers, so although it works, it is not stable and may break
        # somewhere, sometimes.
        cdata = audio_buffer.constData()
        (dtype, ctype, num_bytes, num_frames,
         bytes_per_frame, sample_rate) = self.get_buffer_info(audio_buffer)
        pointer_addr_str = str(cdata).split("Address ")[1].split(", Size")[0]
        pointer_addr = int(pointer_addr_str, 16)
        arr = np.array((ctype * num_frames).from_address(pointer_addr)).copy()
        #
        self.result.append(arr)
        self.sample_rate = sample_rate
