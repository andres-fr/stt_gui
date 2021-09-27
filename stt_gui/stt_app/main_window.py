#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
This module implements the main app widget that contains and manages all other
widgets, the ``MainWindow`` class.
"""


from PySide2 import QtCore, QtWidgets, QtGui
#
from .dialogs import InstructionsDialog, AboutDialog, KeymapsDialog
#
from .audio_manager import AudioManager
from .text_editor import TextEditor
from .profiles import  ProfileList
from .profiles.to_upper import ToUpperProfile
from .profiles.to_lower import ToLowerProfile
# from .profiles.example import ExampleProfile
from .profiles.wav_to_text_silero import WavToTextSileroProfile


# #############################################################################
# ## MAIN WINDOW
# #############################################################################
class MainWindow(QtWidgets.QMainWindow):
    """
    This class is a composition of 3 main elements: text editor, audio manager
    and profile list. It also provides an undo stack and a series of
    keybindings, as well as a menu bar with dialogs and actions.

    Also importantly, the ``__init__`` method is responsible for defining the
    ``profile types`` that will be included in the ``ProfileList``. Note that
    these are not instances, but factories, since the profile list can have
    multiple of the same type.
    """

    def __init__(self, parent=None, delta_secs=2, font_size=12):
        """
        """
        super().__init__(parent)
        self._setup_undo()
        #
        self.text_editor = TextEditor(self, font_size=font_size,
                                      external_undo_stack=self.undo_stack)
        self.audio_manager = AudioManager(self, delta_secs)
        # This is where we present the profile types that will be used.
        # Since they are not instances, we must bind them together through
        # class attributes whenever needed.
        to_upper_prof = ToUpperProfile
        to_upper_prof.TEXT_EDITOR = self.text_editor
        #
        to_lower_prof = ToLowerProfile
        to_lower_prof.TEXT_EDITOR = self.text_editor
        #
        wtt_silero_prof = WavToTextSileroProfile
        wtt_silero_prof.TEXT_EDITOR = self.text_editor
        wtt_silero_prof.AUDIO_MANAGER = self.audio_manager
        self.profiles = ProfileList(
            self, [wtt_silero_prof, to_upper_prof, to_lower_prof])
        #
        self.instructions_dialog = InstructionsDialog()
        self.about_dialog = AboutDialog()
        self.keymaps_dialog = KeymapsDialog(
            {k: v.toString() for k, v in self.keymaps().items()})
        # # create main layout, add controller and graphics:
        self.main_splitter = QtWidgets.QSplitter()
        self.main_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.main_splitter.addWidget(self.profiles)
        self.main_splitter.addWidget(self.text_editor)
        self.main_splitter.addWidget(self.audio_manager)
        #
        self.setCentralWidget(self.main_splitter)
        #
        self._setup_menu_bar()
        self._add_keymaps()
        #
        self.text_editor.eventCatched.connect(self.on_catched_editor_event)

    def on_catched_editor_event(self, evt):
        """
        The ``TextEditor`` includes functionality to bypass built-in key events.
        Whenever they are bypassed, they land here and  our custom keybindings
        will be able to catch it.
        """
        if evt.type() == QtCore.QEvent.KeyPress:
            QtCore.QCoreApplication.sendEvent(self, evt)

    def _setup_undo(self):
        """
        Set up undo stack and undo view
        """
        self.undo_stack = QtWidgets.QUndoStack(self)
        self.undo_view = QtWidgets.QUndoView(self.undo_stack)
        self.undo_view.setWindowTitle("Undo View")
        self.undo_view.setAttribute(QtCore.Qt.WA_QuitOnClose, False)

    def _setup_menu_bar(self):
        """
        Set up menu bar: create actions and connect them to methods.
        """
        # edit menu
        edit_menu = self.menuBar().addMenu("Edit")
        self.open_txt_action = edit_menu.addAction("Open text")
        self.open_txt_action.triggered.connect(self.text_editor.load_dialog)
        self.save_txt_action = edit_menu.addAction("Save text")
        self.save_txt_action.triggered.connect(self.text_editor.save_dialog)
        self.quicksave_txt_action = edit_menu.addAction("Quicksave text")
        self.quicksave_txt_action.triggered.connect(self.text_editor.quicksave)
        edit_menu.addSeparator()
        self.undo_action = edit_menu.addAction("Undo")
        self.undo_action.triggered.connect(self.undo_stack.undo)
        self.redo_action = edit_menu.addAction("Redo")
        self.redo_action.triggered.connect(self.undo_stack.redo)
        edit_menu.addSeparator()
        self.view_undo_action = edit_menu.addAction("View undo stack")
        self.view_undo_action.triggered.connect(self.undo_view.show)
        # run menu
        run_menu = self.menuBar().addMenu("Run")
        self.run_selected_profile = run_menu.addAction("Run selected profile")
        self.run_selected_profile.triggered.connect(self.profiles.run_selected)
        run_menu.addSeparator()
        self.toggle_play_action = run_menu.addAction("Toggle play/pause")
        self.toggle_play_action.triggered.connect(
            self.audio_manager.player.play_b.click)
        self.bw_action = run_menu.addAction("Seek player back <<")
        self.bw_action.triggered.connect(self.audio_manager.player.bw_b.click)
        self.fw_action = run_menu.addAction("Seek player forward >>")
        self.fw_action.triggered.connect(self.audio_manager.player.fw_b.click)
        self.record_action = run_menu.addAction("Record audio")
        self.record_action.triggered.connect(self.audio_manager.record_b.click)
        # help menu
        help_menu = self.menuBar().addMenu("Help")
        self.keyboard_shortcuts = help_menu.addAction("Keyboard shortcuts")
        self.keyboard_shortcuts.triggered.connect(self.keymaps_dialog.show)
        self.instructions = help_menu.addAction("Instructions")
        self.instructions.triggered.connect(self.instructions_dialog.show)
        self.about = help_menu.addAction("About")
        self.about.triggered.connect(self.about_dialog.show)

    def keymaps(self):
        """
        :returns: A dictionary in the form ``name: QtGui.QKeySequence``.

        Define this GUI's specific key mappings. Note that this method can
        be overriden to return a different mapping, but the ``name``s have
        to remain identical, in order to be recognized by ``_add_keymaps``.
        """
        d = {
            "Undo": QtGui.QKeySequence("Ctrl+Z"),
            "Redo": QtGui.QKeySequence("Ctrl+Y"),
            "View undo stack": QtGui.QKeySequence("Alt+Z"),
            #
            "Open text": QtGui.QKeySequence("Ctrl+O"),
            "Save text": QtGui.QKeySequence("Ctrl+S"),
            "Quicksave text": QtGui.QKeySequence("Ctrl+Shift+S"),
            #
            "Run selected profile": QtGui.QKeySequence("Ctrl+Return"),
            #
            "Toggle play/pause": QtGui.QKeySequence("Ctrl+Space"),
            "Seek player back <<": QtGui.QKeySequence("Ctrl+Left"),
            "Seek player forward >>": QtGui.QKeySequence("Ctrl+Right"),
            "Record audio": QtGui.QKeySequence("Ctrl+R")
        }
        return d

    def _add_keymaps(self):
        """
        This function is closely connected to ``keymaps``. There, the
        shortcuts are defined, here, they are applied.
        """
        km = self.keymaps()
        # add menu shortcuts
        self.save_txt_action.setShortcut(km["Save text"])
        self.quicksave_txt_action.setShortcut(km["Quicksave text"])
        self.open_txt_action.setShortcut(km["Open text"])
        #
        self.undo_action.setShortcut(km["Undo"])
        self.redo_action.setShortcut(km["Redo"])
        self.view_undo_action.setShortcut(km["View undo stack"])
        #
        self.run_selected_profile.setShortcut(km["Run selected profile"])

        self.toggle_play_action.setShortcut(km["Toggle play/pause"])
        self.bw_action.setShortcut(km["Seek player back <<"])
        self.fw_action.setShortcut(km["Seek player forward >>"])
        self.record_action.setShortcut(km["Record audio"])
