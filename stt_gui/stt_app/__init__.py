# -*- coding:utf-8 -*-


"""
"""


import os


with open(os.path.join(os.path.dirname(__file__),
                       "assets", "instructions.txt"), "r") as f:
    INSTRUCTIONS = f.read()
with open(os.path.join(os.path.dirname(__file__),
                       "assets", "about.txt"), "r") as f:
    ABOUT = f.read()
