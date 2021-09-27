#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
This module implements a simple example of a profile with dummy functionality
for illustration purposes.
"""


import time
#
from ...dialogs import InfoDialog
from . import Profile, ProfileDialog, ProfileWorker
from ...widgets import WidgetWithValueState, BoolCheckBox, IntSpinBox

# #############################################################################
# ## WORKER
# #############################################################################
class ExampleWorker(ProfileWorker):
    """
    The worker is the object that actually runs the computations in a separate
    thread.
    """
    def run(self, quack, quack_count, minval, maxval):
        """
        """
        result = "Result of example computation"
        nvals = maxval - minval
        if quack:
            for i in range(quack_count):
                if self._abort:
                    return
                self.update_progress(int(i / quack_count * nvals) + minval)
                result += f"\n{i+1} Quack!"
                time.sleep(0.1)
        return result


# #############################################################################
# ## FORM COMPONENTS
# #############################################################################
class PositiveIntSpinBox(IntSpinBox, WidgetWithValueState):
    """
    """
    def __init__(self, parent=None, minimum=-1_000_000, maximum=1_000_000,
                 step=1, default=0, suffix=""):
        """
        """
        super().__init__(parent, 1, maximum, step, default, suffix)


# #############################################################################
# ## PROFILE
# #############################################################################
class ExampleProfile(Profile):
    """
    """
    NAME = "Example Profile"
    SIGNATURE = [("Quack?", BoolCheckBox, False),
                 ("Quack count", PositiveIntSpinBox, 10)]

    def run(self):
        """
        """
        # We will run jobs through the GUI dialog to showcase it
        dialog = ProfileDialog(
            self, body_text="Running example...",
            with_progress_bar=True, default_accept_button=False)
        # Extract state from dialog and form
        minval, maxval = dialog.PROGRESS_BAR_RANGE
        form_dict = self.form.get_state()
        quack = form_dict["Quack?"]
        quack_count = form_dict["Quack count"]
        # Create and run worker!
        worker = ExampleWorker(quack, quack_count, minval, maxval)
        self.run_worker(worker, dialog=dialog)

    def on_accept(self, result):
        """
        """
        dialog = InfoDialog(
            "User accepted!", "(press OK to continue)",
            accept_button_name="OK", print_msg=False)
        dialog.accept_b.setDefault(True)
        dialog.exec_()
