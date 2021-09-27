#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
This module implements the machinery for this app's plugin system (the
 "profiles"). This docstring explains the main components of the plugin system,
 and how to create new plugins. Its main features are:

* Users can create/delete multiple instances of the same profile type. This may
  be useful when the same function with different parameters must be run often.
* Jobs are performed by "workers" on separate threads. This prevents jobs from
  blocking the main app, and allows users to get real-time information about
  the progress and abort the job at any time
* Optionally, users can be allowed to inspect the job while it's running, and
  confirm/reject the results before applying any changes.

This is implemented through 4 pieces:

1. ``ProfileList``: This is the dynamic container that allows users to add,
  delete, select and run profiles. It features ``Profile`` classes, and
  instantiates/deletes them depending on user input. It is usually the access
  point to the whole plugin system, all user interaction goes through this
  object.

2. ``Profile``: The entries of ``ProfileList``. They consist of a name, a
  signature that tells which parameters can be given by the user through the
  GUI, and the machinery to run the job using those parameters, as well as
  functionality to execute changes on the application based on the job
  results. It is the central building block of the plugin system.

3. ``ProfileWorker``: A functor designed to run a job on a different thread.
  It features a ``run(parameters...) -> result`` method that implements the
  functionality to be run.
  The ``Profile.run_worker`` method allows to run it on a different thread and
  handle the results, either by applying them directly, or by running the worker
  through a ``ProfileDialog`` for a more interactive graphical experience.

4. ``ProfileDialog``: The graphical way of running a job. It displays the
  current name and parameters being run, and optionally a progress bar. Once
  the results are done, it also displays them and asks user for confirmation
  before telling the ``Profile`` to execute the changes.

The following steps are the expected way to create a new plugin (see existing
ones for examples):

1. Extend the ``ProfileWorker`` class implementing the desired functionality
   at the ``run(parameters) -> result`` method. The ``update_progress(int)``
   method can be used to update the progress bar if the worker runs on a
   ``ProfileDialog``. Also, for longer jobs, check the ``worker._abort`` flag
   periodically, and if it is True, return as soon as possible.

2. Extend the ``Profile`` class and override at least the following:
  a) ``NAME, SIGNATURE`` class attributes: the name is a string, and signature
     is a list of ``(param_name, param_widget)`` tuples that will be displayed
     so that users can provide parameters through the GUI (see ``NamedForm``
     docstring for more info on the signature).
  b) ``on_accept(result) -> None``: Given the results from the worker, this
    method applies the desired changes. Note that the ``Profile`` constructor
    is only called when the user adds a profile to the profile list and not
    before, so pointers to the main application will usually have to be given+
    as class attributes.
  c) ``run() -> None``: The core of the operation. Usually it starts gathering
    any state from the app and parameters from ``profile.form``. Then, it must
    instantiate the worker. Note that the arguments for the ``worker.run``
    method must be passed here to the worker constructor! ``run_worker`` will
    take care of passing them over to ``worker.run`` once it has been sent to
    a different thread. Then, optionally create a ``ProfileDialog`` instance
    if the job is to be run interactively. Finally, call ``profile.run_worker``
    providing the worker (and optionally the dialog).

3. With points 1 and 2 we are done with the plugin. On the main app, we only
   need now to add the newly created ``Profile`` to the ``ProfileList`` widget.
   Once the app is running, the new profile should be visible on the list. Note
   that this is the place to add any app-related class attributes to the
   ``Profile`` classes, if required (e.g. a reference to a widget that the
   profile will modify).
"""


import time
#
from PySide2 import QtWidgets, QtCore
#
from ...widgets import StrLenSpinBox, PvalueSpinBox, BoolCheckBox, NamedForm
from ...widgets import ScrollbarList, get_separator_line, get_scroll_area
from ...dialogs import FlexibleDialog
from ...utils import recursive_delete_qt


# #############################################################################
# ## PROFILE LIST
# #############################################################################
class ProfileList(ScrollbarList):
    """
    A simple ``ScrollbarList`` that allows GUI users to interact with the
    profiles. Note that zero configuration takes place here,
    see the module docstring for more details. Usage example, from the
    widget that controlles this list::

      profile1 = SomeProfile
      profile2 = SomeOtherProfile
      self.profile_list = ProfileList(self, [profile1, profile2])

    Then, if the list is exposed to the users, they will be able to create,
    remove, select and run selected profiles through the GUI.
    """

    def __init__(self, parent, profiles=[]):
        """
        :param profiles: A collection of ``Profile`` classes (not instances).
          They must provide a parameterless constructor, and a parameterless
          ``run()`` method.
        """
        self.profile_names = [p.NAME for p in profiles]
        self.profiles = profiles
        super().__init__(parent, horizontal=False)
        #
        self.sel_group = QtWidgets.QButtonGroup(self)
        #
        self.run_b = QtWidgets.QPushButton("Run Selected")
        self.run_b.pressed.connect(self.run_selected)
        self.main_layout.addWidget(self.run_b)

    def setup_adder_layout(self, lyt):
        """
        """
        # Create the combobox and the add button that reads the current
        # combobox value
        cbox = QtWidgets.QComboBox()
        cbox.addItems(self.profile_names)
        add_b = QtWidgets.QPushButton("Add Profile")
        # add cbx and button to layout
        lyt.addWidget(cbox)
        lyt.addWidget(add_b)
        # and connect button to cbox and add_element:
        def cbox_to_add():
            idx = cbox.currentIndex()
            profile = self.profiles[idx]()
            self.add_element(profile)
        add_b.pressed.connect(cbox_to_add)

    def add_element(self, profile):
        """
        """
        self.list_layout.addWidget(profile)
        # add "select" and "delete" buttons
        sel_b = QtWidgets.QRadioButton("Select")
        self.sel_group.addButton(sel_b)
        profile.left_layout.addWidget(sel_b)
        remove_b = QtWidgets.QPushButton("Delete")
        profile.left_layout.addWidget(remove_b)
        # connect "delete" button
        remove_b.pressed.connect(
            lambda: self.delete_profile(profile))
        # select added element
        sel_b.click()

    def delete_profile(self, profile):
        """
        """
        layout_idx = self.list_layout.indexOf(profile)
        p = self.list_layout.takeAt(layout_idx)
        recursive_delete_qt(p)

    def run_selected(self):
        """
        """
        selected = self.sel_group.checkedButton()
        if selected is not None:
            profile = selected.parent()
            profile.run()


# #############################################################################
# ## PROFILE
# #############################################################################
class Profile(QtWidgets.QWidget):
    """
    The application allows users to create and remove multiple copies of the
    same type of plugin, called here a ``Profile``, and managed by a
    ``ProfileList``. The list expects profiles given to be parameterless
    factories, and the resulting instances to provide a parameterless ``run()``
    method.

    The following is expected when extending this class:

    * Override the ``NAME, SIGNATURE`` class attributes with the displayed
      name and form signature of the profile to be implemented.
    * Override the ``on_accept`` method

    :cvar str NAME: Name of this profile
    :cvar list SIGNATURE: Input to this profile's ``NamedForm``
    """

    NAME = "Example Profile"
    SIGNATURE = [("max_length", StrLenSpinBox, 10),
                 ("P-value", PvalueSpinBox, 0.5),
                 ("reverse", BoolCheckBox, True)]

    def __init__(self, line_below=True, parent=None):
        """
        """
        super().__init__(parent=parent)
        # create central widget: the form
        self.form = NamedForm(self.NAME, self.SIGNATURE)
        # create and connect all layouts
        # main_vert[ inner_horiz(left, form, right), line  ]
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.inner_layout = QtWidgets.QHBoxLayout()
        self.left_layout = QtWidgets.QVBoxLayout()
        self.right_layout = QtWidgets.QVBoxLayout()
        self.main_layout.addLayout(self.inner_layout)
        self.inner_layout.addLayout(self.left_layout)
        self.inner_layout.addWidget(self.form)
        self.inner_layout.addLayout(self.right_layout)
        # optionally draw a line below main layout
        if line_below:
            self.main_layout.addWidget(get_separator_line(horizontal=True))
        # and finally populate left/right layouts
        self.setup_left(self.left_layout)
        self.setup_right(self.right_layout)

    def run_worker(self, worker, dialog=None):
        """
        """
        # worker will be on a different thread, so we connect it to
        # send the results to the appropriate destiny
        if dialog is None:
            # if no dialog given, directly run on_accept with results
            worker.resultSignal.connect(self.on_accept)
        else:
            worker.resultSignal.connect(dialog.on_finished_worker)
            worker.progressSignal.connect(dialog.update_progress)
            dialog.abortWorkerSignal.connect(worker.abort)
        # move worker to a thread, start worker and open this dialog
        thread = worker.thread
        worker.moveToThread(thread)
        thread.started.connect(worker.wrapped_run)
        thread.start()
        if dialog is not None:
            dialog_ok = dialog.exec_()
            if not dialog_ok:
                dialog.abortWorkerSignal.emit()
        # When the worker is done, it will trigger the "on_finished_worker"
        # method: if user accepts results, they will be sent back to
        # profile.on_accept for final processing.
        # Now it's time to close the thread. The standard way of doing that
        # is calling quit, then wait.
        thread.quit()
        successful_thread = thread.wait()
        if not successful_thread:
            print("WARNING: thread wasn't closed successfully, ",
                  "this may lead to segfaults")

    def setup_right(self, lyt):
        """
        :param lyt: The right side layout. Usually it just contains the Run
          button
        """
        self.run_b = QtWidgets.QPushButton("Run")
        lyt.addWidget(self.run_b)
        self.run_b.pressed.connect(self.run)

    def setup_left(self, lyt):
        """
        :param lyt: The left side layout. Optionally add here any GUI elements
          to expose any specific functionality for the profile (default empty)
        """
        pass

    def run(self):
        """
        """
        pass

    def on_accept(self, result):
        """
        :param result: Output from running the ``ProfileWorker.run`` method.

        This method should be overriden with the desired outcome given the
        result of running the worker (e.g. given a pointer to the text editor,
        paste the result into current location).
        """
        print("Result accepted!", result)


# #############################################################################
# ## WORKER
# #############################################################################
class ProfileWorker(QtCore.QObject):
    """
    This class is a Qt functor designed to be run by the ``ProfileDialog``
    on a different thread via the ``dialog.run_worker(w)`` method. To
    extend this class, simply override the ``run() -> result`` method and
    provide any ``*args, **kwargs`` used in run to the constructor.

    Note for longer running jobs running through ``ProfileDialog``: It is good
    practice to inform users about the progress, and to allow users aborting
    the job. For this, the following code can be added to ``worker.run``:

      if self._abort:
          return
      self.update_progress(i)
    """
    progressSignal = QtCore.Signal(int)
    resultSignal = QtCore.Signal(object)

    def __init__(self, *run_args, **run_kwargs):
        """
        """
        super().__init__()
        # the thread has to have the same lifespan as the worker, otherwise
        # they crash. To handle this, each worker has its own thread.
        self.thread = QtCore.QThread()
        self.args = run_args
        self.kwargs = run_kwargs
        self._abort = False

    @QtCore.Slot()
    def abort(self):
        """
        If this slot is invoked, the ``_abort`` variable will be set to True.
        This can be used by ``run`` to prematurely finish the job.
        """
        self._abort = True

    def update_progress(self, val):
        """
        Emits the given integer value via ``progressSignal``.
        """
        self.progressSignal.emit(val)

    def wrapped_run(self):
        """
        Result of run is always emitted via resultSignal.
        """
        result = self.run(*self.args, **self.kwargs)
        self.resultSignal.emit(result)

    def run(self, *args, **kwargs):
        """
        Parameterless method that returns the result of computation.
        """
        raise NotImplementedError(
            "Check ExampleProfile for an implementation example")


# #############################################################################
# ## DIALOG
# #############################################################################
class ProfileDialog(FlexibleDialog):
    """
    This dialog orchestrates the whole process of running a profile from the
    GUI. The profile must instantiate a ``ProfileWOrker`` and a
    ``ProfileDialog``, and then call ``run_worker(w, w_args)``. Once running,
    it first informs users about the profile and parameters being run.
    Then, starts a separate thread and runs worker there. Once results are
    back from the thread, it displays them via ``setup_result_layout``. If
    user accepts results, they are sent back to the profile.

    If the worker's result is not a string, the ``setup_result_layout``
    must be overriden.

    .. note::
      The added complexity is mainly due to the fact that the worker must run
      on another thread, and we want users to have the chance to confirm. For
      faster computations that don't require confirmation, profiles can run
      workers directly without the need of this dialog.
    """
    HEADER_TXT = "Running '{}' Profile:"
    RESULT_HEADER_TXT = "Result:"
    ACCEPT_BUTTON_TXT = "Accept"
    REJECT_BUTTON_TXT = "CANCEL"
    WAITING_TXT = "Processing..."
    PROGRESS_BAR_RANGE = (0, 100)

    abortWorkerSignal = QtCore.Signal()

    def __init__(self, profile,
                 body_text = "",
                 with_progress_bar=False,
                 title_style="font-weight: bold; color: black",
                 default_accept_button=True):
        """
        :param progress_bar_range: If not None, a ``(min, max)`` integer pair
        :param default_accept_button: If true, pressing enter will click accept.
          Otherwise it will click reject.
        """
        self.with_progress_bar = with_progress_bar
        self.profile = profile
        self.body_text = body_text
        self.title_style = title_style
        self.default_accept_button = default_accept_button
        super().__init__(reject_button_name=self.REJECT_BUTTON_TXT,
                         parent=profile)

    @staticmethod
    def get_params_table(params_dict):
        """
        """
        params_table = QtWidgets.QTableWidget()
        params_table.setRowCount(len(params_dict) + 1)
        params_table.setColumnCount(2)
        params_table.setItem(0, 0, QtWidgets.QTableWidgetItem("PARAMETER"))
        params_table.setItem(0, 1, QtWidgets.QTableWidgetItem("VALUE"))
        for i, (k, v) in enumerate(params_dict.items(), 1):
            params_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(k)))
            params_table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(v)))
        return params_table

    def get_title_label(self, txt):
        """
        """
        lbl = QtWidgets.QLabel(txt)
        lbl.setStyleSheet(self.title_style)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        return lbl

    def get_waiting_layout(self):
        """
        """
        lyt = QtWidgets.QVBoxLayout()
        if self.with_progress_bar:
            self.waiting_widget = QtWidgets.QProgressBar()
            self.waiting_widget.setRange(*self.PROGRESS_BAR_RANGE)
        else:
            self.waiting_widget = self.get_title_label(self.WAITING_TXT)
        lyt.addWidget(self.waiting_widget)
        return lyt

    def setup_ui_body(self, widget):
        """
        """
        main_layout = QtWidgets.QVBoxLayout(widget)
        #
        self.header_lbl = self.get_title_label(
            self.HEADER_TXT.format(self.profile.NAME))
        self.line1 = get_separator_line(horizontal=True)
        self.body = QtWidgets.QLabel(self.body_text)
        self.line2 = get_separator_line(horizontal=True)
        self.waiting_layout = self.get_waiting_layout()
        self.result_layout = QtWidgets.QVBoxLayout()
        self.progress_area = QtWidgets.QVBoxLayout()
        self.line3 = get_separator_line(horizontal=True)
        # we start showing the wait layout, and once done we show the result
        self.progress_area.addLayout(self.waiting_layout)
        self.progress_area.addLayout(self.result_layout)
        # add elements to main layout
        main_layout.addWidget(self.header_lbl)
        main_layout.addWidget(self.body)
        # Create/add table with parameters only if form had parameters
        form_state = self.profile.form.get_state()
        if form_state:
            main_layout.addWidget(self.line1)
            self.params_table = self.get_params_table(
                self.profile.form.get_state())
            main_layout.addWidget(self.params_table)
        #
        main_layout.addWidget(self.line2)
        main_layout.addLayout(self.progress_area)
        main_layout.addWidget(self.line3)

    @QtCore.Slot(int)
    def update_progress(self, step):
        """
        Call this with an int to update progress bar.
        """
        if self.with_progress_bar:
            minval, maxval = self.PROGRESS_BAR_RANGE
            assert minval <= step <= maxval, \
                f"{step} not in progress bar range {(minval, maxval)}!"
            self.waiting_widget.setValue(step)

    @QtCore.Slot(object)
    def on_finished_worker(self, result):
        """
        Show results and await for user confirmation/cancel.
        """
        # create and add title to result layout
        title = self.get_title_label(self.RESULT_HEADER_TXT)
        self.result_layout.addWidget(title)
        # create scrollbar area for results
        scroller, scroller_widget = get_scroll_area(True, True)
        scroller_lyt = QtWidgets.QVBoxLayout()
        scroller_widget.setLayout(scroller_lyt)
        # retrieve result as implemented by user and add it to scroller_lyt
        result_w = self.setup_result_layout(result)
        scroller_lyt.addWidget(result_w)
        self.result_layout.addWidget(scroller)
        # create, add and connect "accept" button
        self.accept_but = QtWidgets.QPushButton(self.ACCEPT_BUTTON_TXT)
        self.result_layout.addWidget(self.accept_but)
        self.accept_but.pressed.connect(lambda: self.on_accept(result))
        if self.default_accept_button:
            self.accept_but.setDefault(True)
        else:
            self.reject_b.setDefault(True)
        # now we're showing the result, hide waiting widget
        self.waiting_widget.setVisible(False)

    def on_accept(self, result):
        """
        Call on_accept at the profile and close this dialog.
        """
        self.profile.on_accept(result)
        self.accept()

    # Override this if you don't want to show the result text in a label
    def setup_result_layout(self, result):
        """
        Override this method to show the results.
        :returns: A widget containing the results. It will be displayed on the
          dialog.
        """
        result_lbl = QtWidgets.QLabel(result)
        result_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        return result_lbl
