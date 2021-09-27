# -*- coding:utf-8 -*-


"""
This module contains definitions for different kinds of dialogs and related
components that are specific to this application.
"""


import os
#
from PySide2 import QtWidgets, QtGui
#
from . import INSTRUCTIONS, ABOUT
from . import __path__ as ROOT_PATH
from ..dialogs import InfoDialog, FlexibleDialog


# #############################################################################
# ## HELP DIALOGS
# #############################################################################
class InstructionsDialog(InfoDialog):
    """
    Info dialog showing instructions
    """
    def __init__(self):
        """
        """
        super().__init__("INSTRUCTIONS", INSTRUCTIONS, print_msg=False)


class AboutDialog(InfoDialog):
    """
    Info dialog showing about section
    """
    EPSRC_LOGO_PATH = os.path.join(ROOT_PATH[0], "assets", "EPSRC_logo.png")

    def __init__(self):
        """
        """
        super().__init__("ABOUT", ABOUT, print_msg=False)
        logo_label = self.get_logo_label(self.EPSRC_LOGO_PATH)
        self.ui_widget.layout().addWidget(logo_label)

    @staticmethod
    def get_logo_label(img_path, width=250):
        """
        """
        logo = QtGui.QPixmap(img_path)
        logo_label = QtWidgets.QLabel()
        logo_label.setPixmap(logo.scaledToWidth(width))
        return logo_label


class KeymapsDialog(FlexibleDialog):
    """
    Info dialog showing keymap list
    """
    def __init__(self, mappings, parent=None):
        """
        """
        self.mappings = mappings
        super().__init__(parent=parent)

    def setup_ui_body(self, widget):
        """
        """
        lyt = QtWidgets.QVBoxLayout(widget)
        #
        self.list_widget = QtWidgets.QListWidget()
        for k, v in self.mappings.items():
            self.list_widget.addItem("{} ({})".format(k, v))
        lyt.addWidget(self.list_widget)


# #############################################################################
# ## SAVE DIALOGS
# #############################################################################
class SavedInfoDialog(InfoDialog):
    """
    Informative dialog telling about saved paths.
    """
    def __init__(self, save_dict, timeout_ms=500):
        """
        :param save_dict: A dict with ``item_name: save_path`` pairs.
        """
        super().__init__("SAVED", self.save_dict_to_str(save_dict),
                         timeout_ms=timeout_ms,
                         header_style="font-weight: bold; color: green")

    @staticmethod
    def save_dict_to_str(save_dict):
        """
        """
        msg = "\n".join(["Saved {} to {}".format(k, v)
                         for k, v in save_dict.items()])
        return msg


class SaveWarningDialog(InfoDialog):
    """
    A dialog to be prompted when trying to delete unsaved changes.
    Usage example::

      self.dialog = SaveWarningDialog()
      user_wants_to_remove = bool(self.dialog.exec_())
      ...
    """

    def __init__(self):
        """
        """
        super().__init__("WARNING",
                         "DELETE unsaved changes?",
                         "YES, delete and continue", "NO, go back",
                         print_msg=False)
        self.reject_b.setDefault(True)
