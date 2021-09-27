#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
This module implements the ``TextEditor`` class, which contains the
application's text-related functionality. See the class docstring
for more information.
"""


import os
#
from PySide2 import QtWidgets, QtGui, QtCore
#
from ..commands import TextDocumentUndoWrapperCommand
from ..dialogs import InfoDialog


# #############################################################################
# ## TEXT EDITOR
# #############################################################################
class TextEditor(QtWidgets.QPlainTextEdit):
    """
    This class exists because unfortunately the parent class has hardcoded
    behaviour that we can't access directly, so we have to be a bit convoluted
    whenever we want to wrap/extend/bypass such hardcoded behaviour.

    The first issue is that the parent class has several hardcoded built-in key
    events, and some of them may interfer with our app: if a key event is
    handled by the parent app, it won't get propagated anywhere else. To
    prevent that, we add an ``eventFilter``, such that whenever any key event
    fulfills the conditions in the ``catch_keyevent_condition`` method, that
    event won't be handled by this text editor and will be sent out through
    the ``eventCatched`` signal for further handling by the parent class.

    Another issue is that ``QPlainTextEdit`` has a nice built-in undo stack,
    but unfortunately it cannot be accessed or integrated with other undo
    stacks via the Qt API. This class fixes this, as follows:

    1. We do NOT disable the editor's undo/redo functionality.
    2. Every time that this editor adds a Command to its own stack, it fires
       the ``undoCommandAdded(cmd)`` signal. Whenever that happens, we also
       add a ``TextDocumentUndoWrapperCommand(self)`` to the main stack.
    3. Then, every time the user sends an undo/redo event, it will go through
       the main undo stack only. But whenever the undo/redo action is a
       ``TextDocumentUndoWrapperCommand``, it will get passed to the editor
       stack, effectively integrating the editor stack into the external
       stack, and ensuring that both stacks are consistent.

    This class and its usage would be fairly less complex if the parent class
    provided a pointer to access the undo stack. More info::
      https://stackoverflow.com/a/67388173/4511978

    Furthermore, the class incorporates a save and load dialog for text files,
    as well as functionality to insert text blocks, remember the current
    selection, and change the font size.

    :cvar FILENAME_FILTER: Allowed file extensions for the open/save dialogs

    :cvar eventCatched: The ``eventCatched(evt)`` signal (see explanation above)

    :cvar DISABLE_CTRL_KEYS: When pressing ``Ctrl+<KEY>`` for any of the keys in
      this collection, the event will be disabled and sent via ``eventCatched``.
      This is useful e.g. to override built-in keybindings.
    """

    FILENAME_FILTER = "Text files (*.txt *.TXT)"
    DISABLE_CTRL_KEYS = {QtCore.Qt.Key_Left,
                         QtCore.Qt.Key_Right}
    eventCatched = QtCore.Signal(QtCore.QEvent)

    def __init__(self, parent=None, default_savedir=None, font_size=12,
                 external_undo_stack=None):
        """
        """
        super().__init__(parent)
        self.setLineWrapMode(self.WidgetWidth)  # matter of taste
        #
        self.dirpath = (os.path.expanduser("~") if default_savedir is None
                        else default_savedir)
        self.quicksave_path = None  # last path saved. Quicksave will go here
        # custom handle events and emit eventCatched signals
        self.installEventFilter(self)
        self.change_font_size(font_size)
        #
        if external_undo_stack is not None:
            self.external_undo_stack = external_undo_stack
            self.document().undoCommandAdded.connect(self.handle_undo_added)

    # Handling undo stack integration
    def handle_undo_added(self, *args, **kwargs):
        """
        See class docstring.
        """
        cmd = TextDocumentUndoWrapperCommand(self)
        self.external_undo_stack.push(cmd)

    # Handling keyevent bypassing issue
    @classmethod
    def catch_keyevent_condition(cls, keyevt):
        """

        This method implements the conditions for the given key events
        that we want to filter out (see class docstring).
        """
        modifiers = keyevt.modifiers()
        ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        alt = bool(modifiers & QtCore.Qt.AltModifier)
        ctrl_only = ctrl and not shift and not alt
        key = keyevt.key()
        #
        cond1 = ((ctrl and shift and key == QtCore.Qt.Key_Z) or
                 keyevt.matches(QtGui.QKeySequence.Undo) or
                 keyevt.matches(QtGui.QKeySequence.Redo))
        cond2 = ctrl_only and key in cls.DISABLE_CTRL_KEYS
        #
        result = cond1 or cond2
        return result

    def eventFilter(self, obj, evt):
        """
        See class docstring.
        """
        catch = False
        # documentation for keys and modifiers:
        # https://doc.qt.io/qtforpython-5/PySide2/QtCore/Qt.html
        if evt.type() == QtCore.QEvent.KeyPress:
            catch = self.catch_keyevent_condition(evt)
        #
        if catch:
            # block event but send it as signal
            self.eventCatched.emit(evt)
            return True
        else:
            # otherwise act normally
            return super().eventFilter(obj, evt)

    # further functionality
    def selection_details(self):
        """
        If user has selected a region on the text editor, returns
        ``(beginning_idx, end_idx, selected_string)``. Otherwise
        returns ``None``.
        """
        cursor = self.textCursor()
        has_selection = cursor.hasSelection()
        if has_selection:
            beg = cursor.selectionStart()
            end = cursor.selectionEnd()
            sel = cursor.selectedText()
            return beg, end, sel

    def handle_selection_changed(self):
        """
        Interactively listens to user and stores selection details
        """
        cursor = self.textCursor()
        self.selection_beg = cursor.selectionStart()
        self.selection_end = cursor.selectionEnd()
        self.selected_txt = cursor.selectedText()

    def save_text(self, path):
        """
        Saves current contents of text editor to given path.
        """
        with open(path, "w") as f:
            f.write(self.toPlainText())

    def save_dialog(self):
        """
        If called, opens a dialog and lets user choose save path.
        """
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            parent=self, dir=self.dirpath, filter=self.FILENAME_FILTER)
        if filepath:  # if user cancels returns an empty string
            self.dirpath = os.path.dirname(filepath)
            self.save_text(filepath)
            self.quicksave_path = filepath

    def quicksave(self):
        """
        If the editor's contents have been already saved to a path,
        calling quicksave will automatically save to that path.
        """
        if self.quicksave_path is not None:
            self.save_text(self.quicksave_path)
            dialog = InfoDialog(
                "Quicksave", f"Saved text to {self.quicksave_path}",
                timeout_ms=200,
                # accept_button_name="OK",
                print_msg=False)
            dialog.exec_()
        else:
            dialog = InfoDialog(
                "Quicksave", f"No previous path found. Please save first!",
                accept_button_name="OK",
                print_msg=False)
            dialog.accept_b.setDefault(True)
            dialog.exec_()

    def insert_textfile(self, path, delete_current=False):
        """
        """
        with open(path, "r") as f:
            txt = f.read()
            cursor = self.textCursor()
            cursor.insertText(txt)

    def load_dialog(self):
        """
        """
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self, dir=self.dirpath, filter=self.FILENAME_FILTER)
        if filepath:
            self.dirpath = os.path.dirname(filepath)
            self.insert_textfile(filepath, delete_current=False)

    def change_font_size(self, pts=12):
        """
        """
        f = self.font()
        f.setPointSize(pts)
        self.setFont(f)
