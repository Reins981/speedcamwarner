#!/usr/bin/python
# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab

"""
Created on 20.02.2018

@author: reko8680
@Coding Guidelines: Logger methods, functions and variables shall be written in Lowercase separated by _
"""

from __future__ import division
from kivy.clock import Clock
from enum import Enum
import time


class Bcolors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    PURPLE = '\033[95m'
    LIGHTGREEN = '\033[96m'
    BLACK = '\033[97m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class LogLevel(Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"


def add_log_line_to_log_viewer(log_line, log_viewer):
    """
        add a log line to a log viewer
        @param log_line: log line to print (string)
        @param log_viewer: log viewer
        @return: None
    """
    if LogLevel.WARNING.value in log_line or LogLevel.ERROR.value in log_line:
        Clock.schedule_once(lambda dt: log_viewer.add_log(log_line), 0)


def print_log_line_to_stdout(log_line, color=None):
    """
        print a log_line to stdout
        @param log_line: log line to print (string)
        @param color: color to print
        @return: None
    """
    if color == "BLUE":
        print(Bcolors.BLUE + log_line + Bcolors.ENDC)
    elif color == "GREEN":
        print(Bcolors.GREEN + log_line + Bcolors.ENDC)
    elif color == "LIGHTGREEN":
        print(Bcolors.LIGHTGREEN + log_line + Bcolors.ENDC)
    elif color == "WHITE":
        print(Bcolors.BLACK + log_line + Bcolors.ENDC)
    elif color == "YELLOW":
        print(Bcolors.YELLOW + log_line + Bcolors.ENDC)
    elif color == "RED":
        print(Bcolors.RED + log_line + Bcolors.ENDC)
    elif color == "BOLD":
        print(Bcolors.BOLD + log_line + Bcolors.ENDC)
    elif color == "HEADER":
        print(Bcolors.HEADER + log_line + Bcolors.ENDC)
    elif color == "UNDERLINE":
        print(Bcolors.UNDERLINE + log_line + Bcolors.ENDC)
    elif color == "PURPLE":
        print(Bcolors.PURPLE + log_line + Bcolors.ENDC)
    else:
        print(log_line)


class Logger:
    def __init__(self, module_name, log_viewer=None):
        """
        Logger that logs either to stdout or to log_viewer widget
        """
        self.__module_name = module_name
        self.log_viewer = log_viewer
        self.always_log_to_stdout = False

    def set_log_viewer(self, log_viewer):
        self.log_viewer = log_viewer

    def set_configs(self):
        """
        Call this method explicitly from another module if you want to disable logs to stdout
        """
        # Log to stdout event if a log viewer is used
        self.always_log_to_stdout = False

    def create_log_line_prefix(self, log_level):
        """
            create prefix for the log_line containing time and level
            @param log_level: log level (string)
            @return: created log line prefix
        """
        now = time.time()
        ml_sec = repr(now).split('.')[1][:3]
        log_time = time.strftime("%Y-%m-%dT%H:%M:%S.", time.localtime(now))
        log_time = log_time + ml_sec
        log_time += "0" * (23 - len(log_time))  # fill logtime with spaces to get fixed length of chars
        log_line_prefix = log_time + " - [SPEEDMASTER] - "
        log_level += " " * (2 - len(log_level))  # fill level with spaces to get fixed length of chars
        log_line_prefix = log_line_prefix + log_level + " - "

        self.__module_name += " " * (
                    40 - len(self.__module_name))  # fill module_name with spaces to get fixed length of chars
        log_line_prefix = log_line_prefix + self.__module_name + " - "

        return log_line_prefix

    def create_formatted_log_line(self, log_string, log_level="INFO"):
        """
            create a logline with prefix and log informatiion
            @param log_string: log string (string)
            @param log_level: log level (string)
            @return: None
        """
        log_line_prefix = self.create_log_line_prefix(log_level)
        formatted_log_line = log_line_prefix + log_string

        return formatted_log_line

    def print_log_line(self, log_string, log_level="INFO", color=None, log_viewer=None):
        """
            main function to print a logline to a file and to stdout
            @param log_string: log string to print (string)
            @param log_level: log level (string)
            @param color: choose a color if your terminal supports color output (string)
                        (see class Bcolors for list of available colors)
            @param log_viewer: explicit log viewer,
                overrides instance log viewer if both are defined
            @return: None
        """

        log_viewer = log_viewer or self.log_viewer

        log_line = self.create_formatted_log_line(log_string, log_level)

        if log_viewer is None:
            print_log_line_to_stdout(log_line, color)
        else:
            add_log_line_to_log_viewer(log_line, log_viewer)

        if log_viewer is not None and self.always_log_to_stdout:
            print_log_line_to_stdout(log_line, color)
