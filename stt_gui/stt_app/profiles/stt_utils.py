#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
This module gathers various utilities that are specific to the STT-related
plugins (profiles) for this application.
"""


import torch
import torchaudio
import Levenshtein


# ##############################################################################
# # I/O
# ##############################################################################
def read_audio(path: str,
               target_sr = None,
               normalize: bool = True):
    """
    Code modified from https://github.com/snakers4/silero-models
    :param normalize: If given, subtract mean and set max absolute value to 1
    :returns: The pair ``(result_arr, samplerate)``
    """
    wav, sr = torchaudio.load(path)
    if wav.size(0) > 1:
        wav = wav.mean(dim=0, keepdim=True)
    if (target_sr is not None) and (sr != target_sr):
        transform = torchaudio.transforms.Resample(
            orig_freq=sr, new_freq=target_sr)
        wav = transform(wav)
        sr = target_sr
        assert sr == target_sr
    result = wav.squeeze(0)
    if normalize:
        result -= result.mean()
        result /= abs(result).max()
    return result, sr


# ##############################################################################
# # STRING PROCESSING
# ##############################################################################
def merge_overlapping_strings(str1, str2, thresh=1.0, max_range=None):
    """
    :param thresh: Levenshtein similarity threshold, between 0 (none) and
      1 (identical).

    :returns: ``(merged_str, match_size, match_score)``

    Fuzzy string interpolation via Levenshtein metric (if thresh=1, non-fuzzy).
    Checks the Levenshtein similarity between the end of str1 and the beginning
    of str2, increasing the size until either string is consumed or max_range
    is reached. Then it picks the longest match with similarity >= threshold
    as the middle between the non-overlapping parts. Example::

    >>> merge_overlapping_strings("123456789", "778899abcdef", 0.5)
    ('1234567889abcdef', 6, 0.5, '4567889')
    """
    match = 0
    match_score = -1
    if max_range is None:
        max_range = min(len(str1), len(str2))
    #
    for i in range(max_range):
        score = Levenshtein.ratio(str1[-i:], str2[:i])
        if score >= thresh:
            match = i
            match_score = score
    # interpolate the biggest match and put blocks together
    result = str1 + str2[match:]
    # both median and quickmedian are unfortunately very slow
    # interpolation = Levenshtein.median([str1[-match:], str2[:match]])
    # part1 = str1 if match == 0 else str1[:-match]
    # result = part1 + interpolation + str2[match:]
    return result, match, match_score


# ##############################################################################
# # AUDIO SIGNAL PROCESSING
# ##############################################################################
def linear_fade(tnsr, fade_in=0, fade_out=0):
    """
    Given a 1-D tensor, apply a linear fade in/out ratio from
    0 to 1. If a fade of N is given, this means that N samples will
    have less than 1 ratio, and the endpoints will have the lowest
    non-zero factor.

    Therefore adding an N-point fade out to an N-point fade in will
    result in a constant 1 ratio, which is adequate for cross-fading.

    .. warning::
      Operation is performed in-place! It modifies the input.
    """
    device = tnsr.device
    if fade_in > 0:
        ramp_in = torch.linspace(0, 1, fade_in + 2).to(device)
        tnsr[:fade_in + 1] *= ramp_in[1:]
    if fade_out > 0:
        ramp_out = torch.linspace(1, 0, fade_out + 2).to(device)
        tnsr[-fade_out - 1:] *= ramp_out[:-1]


# ##############################################################################
# # WINDOWED INFERENCE
# ##############################################################################
def windowed_run(model, tnsr, max_winsize=160_000, overlap_ratio=0.1,
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
        print(f"windowed_run: processing [{i}/{num_windows}]")
        end = beg + winsize
        chunk = tnsr[beg:end]
        batch *= 0
        batch[:, :len(chunk)] = chunk
        output = chunk_hook(model(batch))
        chunks.append(output)
    return chunks, window_range, winsize, overlap


def windowed_audio_rendering(model, tnsr, max_winsize=160_000,
                             overlap_ratio=0.1, device="cpu"):
    """
    Runs the model on the given tensor with audio data using windowed_run.
    Here it is further assumed that the model receives and returns a tensor of
    shape ``(b, n)``, which should be properly normalized. The model input
    computations will be executed on the given device, but the output will
    be sent to CPU.

    If the tensor is longer than the maximal window size, the computed chunks
    are then sewed together via linear interpolation, based on the given overlap
    ratio.

    A tensor of same type, shape and device as the input is returned.
    """
    chunks, begs, winsize, overlap = windowed_run(model, tnsr, max_winsize,
                                                  overlap_ratio, device)
    # first chunk doesn't have fade-in
    for ch in chunks[1:]:
        linear_fade(ch[0], fade_in=overlap)
    # last chunk doesn't have fade-out
    for ch in chunks[:-1]:
        linear_fade(ch[0], fade_out=overlap)
    #
    result = torch.zeros_like(tnsr, device=tnsr.device)
    len_result = len(result)
    for beg, ch in zip(begs, chunks):
        end = min(beg + winsize, len_result)
        chunksize = end - beg
        result[beg:end] += ch[0][:chunksize].to(result.device)
    #
    return result, begs, winsize, overlap


def windowed_stt_rendering(model, tnsr, max_winsize=160_000,
                           overlap_ratio=0.1, device="cpu",
                           overlap_merge_threshold=0.8,
                           max_overlap_characters=1000):
    """
    Performs a ``windowed_run`` of the ``model`` on the given ``tnsr``,
    and then calls ``merge_overlapping_strings`` to stitch the windowed
    STT results, using the Levenshtein similarity metric.
    :returns: The pair ``(merged_string, match_scores)``, where the scores
      are the Levenshtein similarities.
    """
    chunks, begs, winsize, overlap = windowed_run(
        model, tnsr, max_winsize, overlap_ratio, device,
        chunk_hook=lambda ch: ch[0][0])
    num_chunks = len(chunks)
    #
    merged = ""
    match_scores = []
    for i, ch in enumerate(chunks, 1):
        print(f"Merging texts: [{i}/{num_chunks}]")
        # merged, match_len, match_score, interp
        merged, _, match_score = merge_overlapping_strings(
            merged, ch, overlap_merge_threshold, max_overlap_characters)
        match_scores.append(match_score)
    #
    return merged, match_scores
