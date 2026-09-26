"""
version.py — Single source of truth for the app's name and version.

Other modules import APP_NAME / __version__ from here rather than
hardcoding the string, so renaming or bumping the version only ever
needs to happen in one place.
"""

APP_NAME = "Dearie"
__version__ = "1.0.0"

# (major, minor, patch) tuple form, for any code that wants to compare
# versions numerically rather than as a string.
VERSION_INFO = tuple(int(part) for part in __version__.split("."))
