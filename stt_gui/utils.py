# -*- coding:utf-8 -*-


"""
This module contains helper functions and utilities that may be used anywhere
else in the project.
"""


import io
import os
import itertools
from pathlib import Path
import datetime
#
import numpy as np
from scipy.io import wavfile
import randomcolor
from PySide2 import QtGui, QtCore


# #############################################################################
# ## PURE PYTHON
# #############################################################################
class RandomColorGenerator(randomcolor.RandomColor):
    """
    Flexible generator for nice random colors. For more details check
    https://pypi.org/project/randomcolor/

    Usage example::
      r, g, b = next(RandomColorGenerator().generate(form="rgbArray"))
    """

    def generate(self, hue=None, luminosity=None, count=1, form="rgbArray"):
        """
        :param form: Popular ones: ``rgbArray, rgba, hex, rgb``
        :returns: A generator with ``count`` random colors.

        Overriden to return a generator instead of a list. Source:
          https://github.com/kevinwuhoo/randomcolor-py
        """
        for _ in range(count):
            # First we pick a hue (H)
            H = self.pick_hue(hue)
            # Then use H to determine saturation (S)
            S = self.pick_saturation(H, hue, luminosity)
            # Then use S and H to determine brightness (B).
            B = self.pick_brightness(H, S, luminosity)
            # Then we return the HSB color in the desired format
            yield self.set_format([H, S, B], form)


def unique_filename(path, suffix="_({})", max_iters=10000):
    """
    Given a path, returns the same path if unique, or adds ``(N)`` before the
    extension to make it unique, for ``N`` being the lowest integer possible
    starting from 1.
    """
    if not Path(path).is_file():
        return path
    else:
        prefix, ext = os.path.splitext(path)
        for i in itertools.count(start=1, step=1):
            p = prefix + suffix.format(i) + ext
            if not Path(p).is_file():
                return p
            assert i < max_iters, "max no. of iters reached!"


def seconds_to_timestamp(secs, num_decimals=2):
    """
    Given seconds as a float number, returns a string in the form
    ``hh:mm:ss.xx`` where ``xx`` corresponds to the number of decimals
    given at construction.
    """
    secs, fraction = divmod(secs, 1)
    secs_str = str(datetime.timedelta(seconds=int(secs)))
    frac_str = ("{:." + str(num_decimals) +  "f}").format(
        round(fraction, num_decimals))
    result = secs_str + frac_str[1:]
    return result


class SavedStateTracker:
    """
    Create one of these every time a new state is loaded, call ``edited`` when
    the state has been changed, and ``saved`` when saved.

    The ``saved`` function will optionally show an informative dialog.

    Then call ``delete`` when the state is intended to be deleted. The method
    makes sure that unsaved changes are only deleted with user's confirmation.
    """

    def __init__(self):
        """
        """
        self._dialog = None
        #
        self._has_unsaved_changes = False
        self._has_been_deleted = False

    def edit(self):
        """
        Call this any time the state that we want to track has been edited
        """
        self._has_unsaved_changes = True

    def save(self, saved_dict=None, ok_dialog_ms=1000):
        """
        Call this any time the state that we want to track has been saved
        """
        self._has_unsaved_changes = False
        if saved_dict is not None:
            self.dialog = SavedInfoDialog(saved_dict, ok_dialog_ms)
            self.dialog.show()

    def delete(self):
        """
        Call this when we intend to delete the information that we are
        tracking. If unsaved changes, it will prompt the user to continue.
        """
        if self._has_unsaved_changes:
            self.dialog = SaveWarningDialog()
            user_wants_delete = bool(self.dialog.exec_())
            if not user_wants_delete:
                # in this case the user hit this by mistake, so
                # we return False and do nothing
                return False
        # if we reach this point, it means that either we don't have
        # unsaved changes, or we have but the user is OK with deleting them
        self._has_been_deleted = True
        return True


# #############################################################################
# ## NUMPY <-> QT_PIXMAP INTERFACING
# #############################################################################
def rgb_arr_to_rgb_pixmap(arr):
    """
    :param arr: Expects a ``np.uint8(h, w, 3)`` array.
    :returns: A ``QtGui.QPixmap`` in format ``RGB888(w, h)``.
    """
    h, w, c = arr.shape
    assert c == 3, "Only np.uint8 arrays of shape (h, w, 3) expected!"
    img = QtGui.QImage(arr.data, w, h,
                       arr.strides[0], QtGui.QImage.Format_RGB888)
    pm = QtGui.QPixmap.fromImage(img)
    return pm


def bool_arr_to_rgba_pixmap(arr, rgba=(255, 0, 0, 255)):
    """
    :param arr: Expects a ``np.bool(h, w)`` array.
    :param rgba: 4 values between 0 and 255. Alpha=255 means full opacity.
    :returns: A ``QtGui.QPixmap`` in format ``RGBA8888(w, h)``, where the
      ``false`` values are all zeros and the ``true`` values have the specified
      ``rgba`` color.
    """
    # When painting ``(r, g, b, 0)`` Qt actually paints ``(0, 0, 0, 0)``. The
    # workaround of inverting all pixel values before and after painting
    # didn't work... TODO
    # forum.qt.io/topic/73787/qimage-qpixmal-loses-alpha-color-when-drawing/5
    # also topic/88000/qpainter-loosing-color-of-transparent-pixels-critical
    assert rgba[-1] > 0, "Alpha can't be zero, Qt will delete all :("
    h, w = arr.shape
    marr = np.zeros((h, w, 4), dtype=np.uint8)
    y_idxs, x_idxs = np.where(arr)
    marr[y_idxs, x_idxs] = rgba
    # HERE WOULD COME THE BUGFIX: try harder the "invert colors" approach?
    #
    img = QtGui.QImage(marr.data, w, h, marr.strides[0],
                       QtGui.QImage.Format_RGBA8888)
    #
    pm = QtGui.QPixmap.fromImage(img)
    return pm


def pixmap_to_arr(pm, img_format=QtGui.QImage.Format_RGBA8888):
    """
    :param pm: A Pixmap to be converted
    :param img_format: The ``QtGui.QImage`` format that ``pm`` corresponds to.
      https://doc.qt.io/qtforpython/PySide2/QtGui/QImage.html#image-formats
    :returns: A ``np.uint8(h, w, C)`` array, where the number of channels ``C``
      depends on the image format.

    ..note::
      Pixmaps are in format (w, h, ...) but arrays are returned
      in ``(h, w, ...)``, as usual for numpy
    """
    img = pm.toImage().convertToFormat(img_format)
    w, h = img.size().toTuple()
    arr = np.array(img.constBits()).reshape(h, w, -1)
    return arr


# #############################################################################
# ## AUDIO
# #############################################################################
class QStream(QtCore.QBuffer):
    """
    A stream to make a numpy array playable e.g. in QMediaPlayer, via:

    qstream = QStream(arr, 44100)
    qstream.open()
    QMediaPlayer.SetMedia(QtMultimedia.QMediaContent(), qstream)
    ...
    qstream.close()

    Modified from https://stackoverflow.com/a/63388107/4511978
    """

    READONLY_MODE = QtCore.QIODevice.ReadOnly

    def __init__(self, arr, samplerate, *args, **kwargs):
        """
        :param arr: A float numpy array of rank 1
        :param samplerate: In Hz
        """
        super().__init__(*args, **kwargs)
        # copy the array to bytes
        self.binstream = io.BytesIO()
        wavfile.write(self.binstream, samplerate, arr)
        # copy the bytes to self
        self.setData(self.binstream.getvalue())

    def open(self, mode=None):
        """
        """
        if mode is None:
            mode = self.READONLY_MODE
        super().open(mode)


# #############################################################################
# ## WIDGET HELPERS
# #############################################################################
def recursive_delete_qt(elt):
    """
    QT GUIs form trees of widgets and layouts. Given an element that may be
    a widget or a layout, this function traverses its subtree deleting
    everything recursively. More info::

      https://stackoverflow.com/a/10067548/4511978
    """
    is_widget = elt.widget() is not None
    if is_widget:
        elt.widget().setParent(None)
    else:
        while elt.count():
            item = elt.takeAt(0)
            recursive_delete_qt(item)


def change_label_font(lbl, weight=50, size_pt=None):
    """
    """
    fnt = lbl.font()
    fnt.setWeight(weight)
    if size_pt is not None:
        fnt.setPointSize(size_pt)
    lbl.setFont(fnt)


def resize_button(b, w_ratio=1.0, h_ratio=1.0,
                  padding_px_lrtb=(0, 0, 0, 0)):
    """
    """
    w, h = b.iconSize().toTuple()
    new_w = int(w * w_ratio)
    new_h = int(h * h_ratio)
    new_sz = QtCore.QSize(new_w, new_h)
    b.setIconSize(new_sz)
    #
    left, right, top, bottom = padding_px_lrtb
    b.setStyleSheet(f"padding-left: {left}px;padding-right: {right}px;"
                    f"padding-top: {top}px;padding-bottom: {bottom}px;");
