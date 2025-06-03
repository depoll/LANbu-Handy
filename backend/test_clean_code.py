#!/usr/bin/env python3
"""
Test module with clean Python code that should pass flake8 linting.
"""


def clean_function(param_x, param_y):
    """
    A properly formatted function that follows PEP 8 guidelines.

    Args:
        param_x: First parameter
        param_y: Second parameter

    Returns:
        The sum of param_x and param_y
    """
    result = param_x + param_y
    return result


class CleanClass:
    """A properly formatted class that follows PEP 8 guidelines."""

    def __init__(self):
        """Initialize the class."""
        pass

    def clean_method(self):
        """A clean method with proper formatting."""
        return "This code follows PEP 8 guidelines"


if __name__ == "__main__":
    print("Clean test file")
