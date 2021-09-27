#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
"""


import numpy as np
#
import torch
import torchaudio
#
from PySide2 import QtWidgets, QtCore
#
from ...widgets import WidgetWithValueState, DecimalSpinBox, BoolCheckBox
from ...dialogs import InfoDialog
from . import Profile, ProfileDialog, ProfileWorker
from .stt_utils import merge_overlapping_strings


# #############################################################################
# ## GLOBALS
# #############################################################################
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# #############################################################################
# ## FORM COMPONENTS
# #############################################################################
class DeviceComboBox(QtWidgets.QComboBox):
    """
    """
    def __init__(self, parent, default=DEVICE):
        """
        """
        super().__init__(parent)
        self.addItems(["cpu", "cuda"])
        self.setCurrentText(default)

    def get_state(self):
        """
        """
        return self.currentText()


class WindowSecondsSpinBox(DecimalSpinBox, WidgetWithValueState):
    """
    """
    def __init__(self, parent, default):
        """
        """
        super().__init__(parent, minimum=0, maximum=100000,
                         default=default, step=0.1)


class WindowOverlapRatioSpinBox(DecimalSpinBox, WidgetWithValueState):
    """
    """
    def __init__(self, parent, default):
        """
        """
        super().__init__(parent, minimum=0, maximum=0.99,
                         default=default, step=0.001)


class AmplitudeRatioSpinBox(DecimalSpinBox, WidgetWithValueState):
    """
    """
    def __init__(self, parent, default):
        """
        """
        super().__init__(parent, minimum=0, maximum=10,
                         default=default, step=0.01)


# #############################################################################
# ## CUSTOM DIALOG
# #############################################################################
class NewlinedProfileDialog(ProfileDialog):
    """
    Also expects a text, but breaks it down in new lines if it is too long
    """

    MAX_CHARS_PER_LINE = 100

    def setup_result_layout(self, result):
        """
        Override this method to show the results.
        :returns: A widget containing the results. It will be displayed on the
          dialog.
        """
        rslt = [result[i:i+self.MAX_CHARS_PER_LINE]
                for i in range(0, len(result), self.MAX_CHARS_PER_LINE)]
        rslt = "\n".join(rslt)
        result_lbl = QtWidgets.QLabel(rslt)
        result_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        return result_lbl


# #############################################################################
# ## WORKER
# #############################################################################
class SileroSTT:
    """
    A functor that runs a STT model from Silero, to be used by the worker
    """
    TORCH_HUB_REPO = "snakers4/silero-models"
    EXPECTED_SRATE = 16000

    def __init__(self, model="silero_stt", language="en", device="cpu"):
        """
        """
        self.encoder, self.decoder, utils = torch.hub.load(
            repo_or_dir=self.TORCH_HUB_REPO, model=model,
            language=language, device=device)

    def __call__(self, batch):
        """
        :param batch: Float tensor with 16kHz audio and shape
          ``(batch_size, num_samples)``

        It is possibly beneficial if the audios have zero mean and 0.182 std.
        """
        embeddings = self.encoder(batch)
        texts = [self.decoder(c.to("cpu")) for c in embeddings]
        return texts, embeddings


class WavToTextSileroWorker(ProfileWorker):
    """
    """

    OVERLAP_MERGE_THRESHOLD = 0.9
    MAX_OVERLAP_CHARS = 1000

    def windowed_run(self, model, tnsr, max_winsize=160_000, overlap_ratio=0.1,
                     device="cpu", chunk_hook=lambda ch: ch.to("cpu")):
        """
        :param model: A model with signature``results = model(tensor)``
          for a float batch tensor of shape ``(b, n)``.
        :param tnsr: A 1-D tensor with float audio. Expected to be in adequate
          normalization and frequency for the given model.
        :param overlap_ratio: Overlap between consecutive windows. 0 means no
          overlap, 1 full ovelap.
        :param device: The input to the model (and therefore the computations)
          will be on this device. But the outputs will be sent back to CPU to
          avoid potential GPU overflow.
        :param chunk_hook: Before appending the model output to ``chunks``, it
          is passed through this function.
        :returns: Windowed results, window startpoints, window size.

        This function calls the given model on the given tensor. If the tensor
        is longer than max_winsize, calls the model multiple times for the
        resulting (potentially overlapping) chunks.
        """
        n = len(tnsr)
        winsize = min(max_winsize, n)
        overlap = int(overlap_ratio * winsize)
        stride = winsize - overlap
        #
        chunks = []
        batch = torch.zeros_like(tnsr[:winsize]).unsqueeze(0).to(device)
        window_range = list(range(0, n, stride))
        num_windows = len(window_range)
        for i, beg in enumerate(window_range, 1):
            if self._abort:
                return
            self.update_progress(int(i / num_windows * 100))
            print(f"windowed_run: processing [{i}/{num_windows}]")
            end = beg + winsize
            chunk = tnsr[beg:end]
            batch *= 0
            batch[:, :len(chunk)] = chunk
            output = chunk_hook(model(batch))
            chunks.append(output)
        return chunks, window_range, winsize, overlap

    def windowed_stt_rendering(self, model, tnsr, max_winsize=160_000,
                               overlap_ratio=0.1, device="cpu",
                               overlap_merge_threshold=0.8,
                               max_overlap_characters=1000):
        """
        """
        chunks, begs, winsize, overlap = self.windowed_run(
            model, tnsr, max_winsize, overlap_ratio, device,
            chunk_hook=lambda ch: ch[0][0])
        num_chunks = len(chunks)
        #
        merged = ""
        match_scores = []
        for i, ch in enumerate(chunks, 1):
            if self._abort:
                return
            self.update_progress(int(i / num_chunks * 100))
            print(f"Merging texts: [{i}/{num_chunks}]")
            # merged, match_len, match_score, interp
            merged, _, match_score = merge_overlapping_strings(
                merged, ch, overlap_merge_threshold, max_overlap_characters)
            match_scores.append(match_score)
        #
        return merged, match_scores

    def prepare_arr(self, arr, arr_sr, target_sr, normalize=True):
        """
        :param arr: Numpy audio array.
        Code modified from https://github.com/snakers4/silero-models
        :param normalize: If given, subtract mean and set max abs value to 1
        """
        wav = torch.from_numpy(arr.astype(np.float32))
        if len(wav.shape) == 1:
            wav.unsqueeze_(0)
        if wav.size(0) > 1:
            wav = wav.mean(dim=0, keepdim=True)
        if (target_sr is not None) and (arr_sr != target_sr):
            transform = torchaudio.transforms.Resample(
                orig_freq=arr_sr, new_freq=target_sr)
            wav = transform(wav)
        result = wav.squeeze(0)
        if normalize:
            result -= result.mean()
            result /= abs(result).max()
        return result

    def run(self, wav_arr, wav_arr_srate, max_win_secs, win_overlap_ratio,
            amp_ratio, device):
        """
        """
        stt_model = SileroSTT("silero_stt", "en", device)
        # load whole audio on CPU, shape=n
        whole_audio = self.prepare_arr(wav_arr, wav_arr_srate,
                                       stt_model.EXPECTED_SRATE, normalize=True)
        whole_audio *= amp_ratio
        #
        max_win_samples = int(max_win_secs * stt_model.EXPECTED_SRATE)
        whole_text, _ = self.windowed_stt_rendering(
            stt_model, whole_audio, max_win_samples, win_overlap_ratio,
            device, self.OVERLAP_MERGE_THRESHOLD, self.MAX_OVERLAP_CHARS)
        return whole_text


# #############################################################################
# ## PROFILE
# #############################################################################
class WavToTextSileroProfile(Profile):
    """
    """
    TEXT_EDITOR = None
    AUDIO_MANAGER = None
    NAME = "Speech to text (Silero)"
    SIGNATURE = [("Device", DeviceComboBox, DEVICE),
                 # ("Sample rate", SamplerateSpinBox, 16000),
                 ("Max window seconds", WindowSecondsSpinBox, 60),
                 ("Window overlap ratio", WindowOverlapRatioSpinBox, 0.05),
                 ("Amplitude ratio", AmplitudeRatioSpinBox, 1),
                 ("Record-and-run mode", BoolCheckBox, False)]

    def run(self):
        """
        """
        # sanity check and fetch parameters
        assert self.TEXT_EDITOR is not None, \
            "cls.TEXT_EDITOR needed before instantiation!"
        assert self.AUDIO_MANAGER is not None, \
            "cls.AUDIO_MANAGER needed before instantiation!"
        #
        form_dict = self.form.get_state()
        button_aud_sel = self.AUDIO_MANAGER.get_selected()
        device = form_dict["Device"]
        max_win_secs = form_dict["Max window seconds"]
        win_overlap_ratio = form_dict["Window overlap ratio"]
        amp_ratio = form_dict["Amplitude ratio"]
        record_and_run = form_dict["Record-and-run mode"]
        #
        if record_and_run:
            # if record_and_run, attempt to record wav_arr
            rec_outcome = self.AUDIO_MANAGER.record_audio_array(normalize=True)
            if rec_outcome is None:
                return
            else:
                wav_arr, wav_sr = rec_outcome
        else:
            # otherwise, attempt to fetch wav_arr from the audio manager
            if button_aud_sel is None:
                dialog = InfoDialog(
                    "Missing Audio",
                    "Please load/record/select an audio before running!",
                    accept_button_name="OK", timeout_ms=None, print_msg=False)
                dialog.exec_()
                return
            else:
                aud_elt = button_aud_sel[1]  # ignore the button
                wav_arr, wav_sr = aud_elt.arr, aud_elt.sr
        # If we haven't returned, we have a wav_arr, wav_arr_srate (either
        # recorded or loaded from file) that we can pass to the worker
        dialog = NewlinedProfileDialog(
            self, body_text="Running Silero model...", with_progress_bar=True)
        worker = WavToTextSileroWorker(
            wav_arr, wav_sr, max_win_secs, win_overlap_ratio, amp_ratio, device)
        self.run_worker(worker, dialog=dialog)

    def on_accept(self, result):
        """
        """
        cursor = self.TEXT_EDITOR.textCursor()
        cursor.insertText(result)
