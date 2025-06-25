#!/bin/bash

# Ensure PATH includes .local/bin where uvx is installed
export PATH="$HOME/.local/bin:$PATH"

# Add python alias if not already present
if ! grep -q "alias python='python3'" ~/.bashrc; then
    echo "alias python='python3'" >> ~/.bashrc
fi

# Source bashrc to get aliases
source "$HOME/.bashrc"
