#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
A simple profile that converts any selected text to lowercase.
"""


from ...dialogs import InfoDialog
from . import Profile, ProfileDialog, ProfileWorker


# #############################################################################
# ## WORKER
# #############################################################################
class ToUpperWorker(ProfileWorker):
    """
    """
    def run(self, text):
        result = text.upper()
        return result


# #############################################################################
# ## PROFILE
# #############################################################################
class ToUpperProfile(Profile):
    """
    """
    TEXT_EDITOR = None
    NAME = "To Uppercase"
    SIGNATURE = []

    def run(self):
        """
        """
        assert self.TEXT_EDITOR is not None, \
            "cls.TEXT_EDITOR needed before instantiation!"
        #
        selection = self.TEXT_EDITOR.selection_details()
        if selection is None:
            dialog = InfoDialog(
                "Missing selection",
                "Please select text on the editor before!",
                accept_button_name="OK", timeout_ms=3000, print_msg=False)
            dialog.accept_b.setDefault(True)  # press enter to accept
            dialog.exec_()
        else:
            _, _, selection = selection
            self.run_worker(ToUpperWorker(selection))
            # The 2 lines below run the worker through the dialog instead
            # dialog = ProfileDialog(self, with_progress_bar=False)
            # self.run_worker(ToUpperWorker(selection), dialog=dialog)

    def on_accept(self, result):
        """
        """
        cursor = self.TEXT_EDITOR.textCursor()
        cursor.insertText(result)
