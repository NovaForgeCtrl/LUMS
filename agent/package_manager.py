#!/usr/bin/env python3

import shutil


PACKAGE_MANAGER_APT = "apt"
PACKAGE_MANAGER_PACMAN = "pacman"


def detect_package_manager():
    """
    Detect the package manager available on the client.

    Returns:
        "apt"     when APT is available
        "pacman"  when pacman is available
        None      when no supported package manager is found
    """

    if shutil.which("apt"):
        return PACKAGE_MANAGER_APT

    if shutil.which("pacman"):
        return PACKAGE_MANAGER_PACMAN

    return None
