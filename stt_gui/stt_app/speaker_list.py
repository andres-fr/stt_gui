x#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
This module implements a ``ScrollbarList`` containing ``SpeakerEntry``
elements. It may be useful for diarization plug-ins.
"""


from PySide2 import QtWidgets
#
from ..utils import RandomColorGenerator, recursive_delete_qt
from ..widgets import ScrollbarList


# #############################################################################
# ## SPEAKER ENTRY
# #############################################################################
class SpeakerEntry(QtWidgets.QWidget):
    """
    4 columns: ID, name, color tag, change color
    """
    DEFAULT_NAME = "Speaker_{}"
    MAX_NAME_LENGTH = 20
    MAX_ID_LENGTH = 10

    def __init__(self, index, parent=None, name=None, initial_rgb=None):
        """
        """
        super().__init__(parent)
        # create main layout
        self.main_layout = QtWidgets.QHBoxLayout(self)
        # create user color tag
        self.color_tag = QtWidgets.QLabel()
        self.color_tag.setAutoFillBackground(True)
        self.color_tag.setFixedSize(20, 20)
        self.color_tag.setFrameStyle(
            QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
        self.change_color(initial_rgb)
        # create name text line
        self.name = QtWidgets.QLineEdit()
        self.name.setText(
            self.DEFAULT_NAME.format(index) if name is None else name)
        self.name.setMaxLength(self.MAX_NAME_LENGTH)
        # create ID text line
        self.uid = QtWidgets.QLineEdit()
        self.uid.setText(str(index))
        self.uid.setMaxLength(self.MAX_ID_LENGTH)
        # create change color button
        self.change_color_b = QtWidgets.QPushButton("Change Color")
        # add widgets to parent layout
        self.main_layout.addWidget(self.color_tag)
        self.main_layout.addWidget(self.uid)
        self.main_layout.addWidget(self.name)
        self.main_layout.addWidget(self.change_color_b)
        # connect button to change color
        self.change_color_b.pressed.connect(self.change_color)

    def change_color(self, rgb=None):
        """
        """
        if rgb is None:
            rgb = next(RandomColorGenerator().generate())
        r, g, b = rgb
        self.color_tag.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")
        self.rgb = rgb


# #############################################################################
# ## SPEAKER LIST
# #############################################################################
class SpeakerList(ScrollbarList):
    """
    """
    def __init__(self, parent):
        """
        """
        super().__init__(parent, horizontal=False, add_button_txt="Add Speaker")
        self._new_speaker_idx = 0

    def add_element(self, name=None, initial_rgb=None):
        """
        """
        self._new_speaker_idx += 1
        # create speaker line and its elements
        speaker_layout = QtWidgets.QHBoxLayout()
        remove_speaker_b = QtWidgets.QPushButton("Remove")
        speaker = SpeakerEntry(
            self._new_speaker_idx, name=name, initial_rgb=initial_rgb)
        # add widgets to speaker line
        speaker_layout.addWidget(speaker)
        speaker_layout.addWidget(remove_speaker_b)
        # add speaker line to main list
        self.list_layout.addLayout(speaker_layout)
        # connect remove button to remove this line
        remove_speaker_b.pressed.connect(
            lambda: self.delete_speaker(speaker_layout))

    def delete_speaker(self, speaker_layout):
        """
        """
        layout_idx = self.list_layout.indexOf(speaker_layout)
        child = self.list_layout.takeAt(layout_idx)
        recursive_delete_qt(child)
