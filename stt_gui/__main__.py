# -*- coding:utf-8 -*-


"""
Entry point for the package.
It includes wrapper functions to run full GUI applications, and a dispatcher
that maps CLI parameters to the wrapper functions.
"""


import sys
import argparse
#
from PySide2 import QtWidgets
#
from .stt_app.main_window import MainWindow as STTMainWindow
from .dialogs import ExceptionDialog


def run_stt_app(delta_secs=2, font_size=12):
    """
    Wrapper function that starts the app, wraps execptions, and exits when done.
    """
    app = QtWidgets.QApplication(["Speech-to-text Transcription Tool"])
    mw = STTMainWindow(delta_secs=delta_secs,
                       font_size=font_size)
    mw.show()
    # Wrap any exceptions into a dialog
    sys.excepthook = ExceptionDialog.excepthook
    # run app
    sys.exit(app.exec_())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run different GUIs.")

    parser.add_argument("--app", type=str, default="stt",
                        help="The name of the app you want to run")
    parser.add_argument("--stt_delta_secs", type=float, default=2,
                        help="How many seconds will the fw and bw buttons jump")
    parser.add_argument("--stt_font_size", type=int, default=12,
                        help="Font size for the texts editor, in points")
    args = parser.parse_args()
    #
    APP_NAME = args.app
    STT_DELTA_SECS = args.stt_delta_secs
    STT_FONT_SIZE = args.stt_font_size
    #
    if APP_NAME == "stt":
        run_stt_app(STT_DELTA_SECS, STT_FONT_SIZE)
    else:
        print("Unknown app name!")
