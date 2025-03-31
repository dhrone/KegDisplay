# -*- coding: utf-8 -*-
# Copyright (c) 2024 Ron Ritchey
# See License.rst for details

"""
KegDisplay package for displaying beer information on small screens.

.. versionadded:: 0.0.1
"""

__version__ = '0.1.0'

# Import log_config early to ensure logging is configured
from . import log_config

from .application import Application
from .dependency_container import DependencyContainer 