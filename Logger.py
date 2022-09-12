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
    def __init__(self, module_name):
        self.__module_name = module_name

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
        log_level += " " * (8 - len(log_level))  # fill level with spaces to get fixed length of chars
        log_line_prefix = log_line_prefix + log_level + " - "

        self.__module_name += " " * (
                    50 - len(self.__module_name))  # fill module_name with spaces to get fixed length of chars
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

    def print_log_line(self, log_string, log_level="INFO", color=None):
        """
            main function to print a logline to a file and to stdout
            @param log_string: log string to print (string)
            @param log_level: log level (string)
            @param color: choose a color if your terminal supports color output (string)
                        (see class Bcolors for list of available colors)
            @return: None
        """
        log_line = self.create_formatted_log_line(log_string, log_level)

        print_log_line_to_stdout(log_line, color)
