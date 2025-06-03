#!/usr/bin/env python3

# Test file with intentional flake8 errors for testing pre-commit hook

import os
import sys
import json # unused import

def bad_function( x,y ):  # spaces around parameters
    # line too long - this is a very long line that exceeds the typical 79 character limit used by flake8 for Python code style checking
    result=x+y  # no spaces around operators
    return result

class BadClass:
    def __init__(self):
        pass

    def method_with_issues(self):
        unused_var = "test"  # unused variable
        
        
        # too many blank lines above

if __name__ == "__main__":
    print("Test file with linting errors")