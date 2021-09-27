#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
This module implements the ``AudioManager`` class, which takes care of the
application's audio functionality. It consists of the following elements:

* Dialog to load an audio from the filesystem
* ``AudioRecorderDialog`` to record audio from a device
* A ``ScrollbarList`` that hosts the added ``AudioElements``
* An ``AudioPlayer`` to play the currently selected audio element

The manager itself exposes all audio elements as well as the currently
selected one, and can be used for arbitrary operations on them.
"""


import os
#
import numpy as np
import librosa
from PySide2 import QtCore, QtWidgets
#
from ..audio_player import AudioPlayer
from ..audio_recorder import AudioRecorderDialog
from ..utils import recursive_delete_qt
from ..widgets import ScrollbarList


# #############################################################################
# ## AUDIO ELEMENT
# #############################################################################
class AudioElement(QtWidgets.QWidget):
    """
    4 columns: ID, name, color tag, change color
    """
    MAX_NAME_LENGTH = 20
    MAX_ID_LENGTH = 10

    def __init__(self, name, arr, sr, url=None, parent=None, horizontal=True):
        """
        Audio files can be loaded to the player via URL, but we also want to
        pass audio directly from working memory. This class provides a flexible
        common interface: given an array and samplerate, it generates a stream
        that can be passed to the player, and stores everything as instance
        attributes. It also stores the (optional) URL.

        It is also a widget: displays its name and can be added to layouts.
        """
        super().__init__(parent)
        self.name = name
        self.arr = arr
        self.sr = sr
        self.url = url
        self.horizontal = horizontal
        #
        self._setup_gui()

    def _setup_gui(self):
        """
        """
        # create main layout
        self.main_layout = QtWidgets.QHBoxLayout(self) if self.horizontal \
            else QtWidgets.QVBoxLayout(self)
        # create widgets
        label = f"{self.name} (sr={self.sr})"
        self.name_l = QtWidgets.QLabel(label)
        # add widgets to layout
        self.main_layout.addWidget(self.name_l)

    def duration(self):
        """
        :returns: duration in seconds (decimal number)
        """
        result = float(len(self.arr)) / self.sr
        return result


# #############################################################################
# ## AUDIO MANAGER
# #############################################################################
class AudioManager(ScrollbarList):
    """
    This class integrates 3 parts:
    1. Two dialogs that allow to load audio from the filesystem or record it
    2. A list of currently active audios (loaded or recorded). The list allows
      users to select a particular audio, and to delete any audio
    3. A player that plays the currently selected audio.
    """
    def __init__(self, parent, delta_secs=2,
                 default_dirpath=os.path.expanduser("~"),
                 extension_filter="Audio (*.wav *.WAV *.mp3 *.MP3)"):
        """
        :param float delta_secs: Time jump for the fw and bw buttons
        :param extension_filter: See default or Qt docs for syntax
        """
        super().__init__(parent, horizontal=False)
        self._new_speaker_idx = 0
        #
        self.sel_group = QtWidgets.QButtonGroup(self)
        self.sel_group.buttonPressed.connect(self.on_selected)
        #
        self.player = AudioPlayer(parent=self,
                                  bw_delta_secs=delta_secs,
                                  fw_delta_secs=delta_secs)
        self.main_layout.addWidget(self.player)
        #
        self.dirpath = default_dirpath
        self.filter = extension_filter
        #
        self._recording_idx = 0

    def button_audio_list(self):
        """
        :returns: A list in form ``[(b, a), ...]`` where b is the select
          button and a the corresponding AudioElement widget.
        """
        result = [(x.itemAt(0).widget(), x.itemAt(1).widget())
                  for i, x in enumerate(self.list_layout.children())]
        return result

    def get_selected(self):
        """
        :returns: None if no audio is selected (at instantiation). Otherwise,
          returns the selected ``(button, AudioElement)`` pair.
        """
        checked_b = self.sel_group.checkedButton()
        selected = [(b, aud) for b, aud in self.button_audio_list()
              if b is checked_b]
        if selected:
            return selected[0]

    def on_selected(self, button):
        """
        Gets called when a button is pressed. It sets the selected audio to
        the player.
        """
        # get selected audio element
        ba_list = self.button_audio_list()
        sel_aud = [aud for b, aud in ba_list if (b is button)][0]
        # assign audio stream to player and update widgets
        self.player.set_array(sel_aud.arr, sel_aud.sr)
        # self.player.set_media_stream(sel_aud.qstream)
        self.player.configure_gui(min_val=0, max_val=sel_aud.duration(),
                                  step=0.1, pos_secs=0,
                                  enable_buttons=True)

    def make_dialogs(self):
        """
        GUI setup function, creates and returns the load/record dialog buttons
        """
        # create entry layout
        lyt = QtWidgets.QVBoxLayout() if self.horizontal \
            else QtWidgets.QHBoxLayout()
        # create selection button
        self.load_b = QtWidgets.QPushButton("Load Audiofile")
        self.record_b = QtWidgets.QPushButton("Record Audio")
        # add buttons to layout
        lyt.addWidget(self.load_b)
        lyt.addWidget(self.record_b)
        # connect buttons to functions
        self.load_b.pressed.connect(self.load_audio)
        self.record_b.pressed.connect(self.record_audio)
        #
        return lyt

    def setup_adder_layout(self, lyt):
        """
        Basically a wrapper for make_dialogs
        """
        # create elements
        d_lyt = self.make_dialogs()
        # create sub-layout, add elts to it and add it to adder layout
        self.dialogs_layout = QtWidgets.QHBoxLayout() if self.horizontal \
            else QtWidgets.QVBoxLayout()
        self.dialogs_layout.addLayout(d_lyt)
        # self.dialogs_layout.addWidget(line)
        lyt.addLayout(self.dialogs_layout)

    def add_element(self, widget):
        """
        :param widget: The element to be added.
        Adds given widget to the central list, surrounded by Select and
        Delete buttons, which allow users to edit the list dynamically.
        """
        # create entry layout
        lyt = QtWidgets.QVBoxLayout() if self.horizontal \
            else QtWidgets.QHBoxLayout()
        # create selection button
        sel_b = QtWidgets.QRadioButton("Select")
        self.sel_group.addButton(sel_b)
        # Create and connect delete button
        del_b = QtWidgets.QPushButton("Delete")
        del_b.pressed.connect(lambda: self.delete_element(lyt))
        # add select/widget/delete to element layout
        lyt.addWidget(sel_b)
        lyt.addWidget(widget)
        lyt.addWidget(del_b)
        #
        self.list_layout.addLayout(lyt)

    def delete_element(self, element):
        """
        Used by the Delete buttons in add_element
        """
        layout_idx = self.list_layout.indexOf(element)
        elt = self.list_layout.takeAt(layout_idx)
        recursive_delete_qt(elt)

    def load_audio(self):
        """
        Load from file dialog and action
        """
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self, dir=self.dirpath, filter=self.filter)
        if filepath:
            filename = os.path.basename(filepath)
            # gather audio data/metadata from path
            arr, sr = librosa.load(filepath, sr=None)
            arr -= arr.mean()
            arr /= abs(arr).max()
            url = QtCore.QUrl.fromLocalFile(filepath)
            # create audio entry object
            aud = AudioElement(name=filename, arr=arr, sr=sr,
                               url=url, parent=self, horizontal=True)
            self.add_element(aud)
            # at this point the new (button, widget) is present in the list.
            # find the button and click it to select loaded audio
            ae_button = [b for b, a in self.button_audio_list() if a is aud][0]
            ae_button.click()
            # finally if all went well update dialog dirpath
            self.dirpath = os.path.dirname(filepath)

    def record_audio_array(self, normalize=True):
        """
        Triggers a recorder dialog.
        :param bool normalize: If true, result gets normalized to 0 mean and
          between -1 and 1.
        :returns: If user records AND accepts, returns float32 numpy array with
          the audio recording, and the sample rate.
        """
        rec_outcome, sr = AudioRecorderDialog.record_audio(self)
        if rec_outcome:  # True only if accepted
            rec_outcome = np.concatenate(rec_outcome).astype(np.float32)
            if normalize:
                rec_outcome -= rec_outcome.mean()
                rec_outcome /= abs(rec_outcome).max()
            return rec_outcome, sr

    def record_audio(self, normalize=True):
        """
        """
        rec_outcome = self.record_audio_array(normalize)
        if rec_outcome is not None:
            arr, sr = rec_outcome
            # create audio entry object from recorded array
            self._recording_idx += 1
            aud = AudioElement(f"Recording{self._recording_idx}",
                               arr, sr, parent=self, horizontal=True)
            self.add_element(aud)
            # at this point the new (button, widget) is present in the list.
            # find the button and click it to select loaded audio
            ae_button = [b for b, a in self.button_audio_list() if a is aud][0]
            ae_button.click()
