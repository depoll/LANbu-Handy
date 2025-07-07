#!/bin/bash

# Ensure PATH includes .local/bin where uvx is installed
export PATH="$HOME/.local/bin:$PATH"

# Add python alias if not already present
if ! grep -q "alias python='python3'" ~/.bashrc; then
    echo "alias python='python3'" >> ~/.bashrc
fi

# Configure git completions and prompt if not already present
if ! grep -q "Git completions" ~/.bashrc; then
    cat >> ~/.bashrc << 'EOF'

# Git completions
if [ -f /usr/share/bash-completion/completions/git ]; then
    . /usr/share/bash-completion/completions/git
fi

# Git prompt
if [ -f /usr/lib/git-core/git-sh-prompt ]; then
    source /usr/lib/git-core/git-sh-prompt
    # Show git branch and status
    export GIT_PS1_SHOWDIRTYSTATE=1
    export GIT_PS1_SHOWSTASHSTATE=1
    export GIT_PS1_SHOWUNTRACKEDFILES=1
    export GIT_PS1_SHOWUPSTREAM="auto"
    export GIT_PS1_SHOWCOLORHINTS=1
    export GIT_PS1_DESCRIBE_STYLE="branch"
fi

# Modern visual prompt with powerline-style elements
# Colors
RESET='\[\033[0m\]'
BOLD='\[\033[1m\]'

# Background colors
BG_BLUE='\[\033[44m\]'
BG_GREEN='\[\033[42m\]'
BG_YELLOW='\[\033[43m\]'
BG_RED='\[\033[41m\]'
BG_PURPLE='\[\033[45m\]'
BG_CYAN='\[\033[46m\]'
BG_DARK_GRAY='\[\033[100m\]'

# Foreground colors
FG_WHITE='\[\033[97m\]'
FG_BLACK='\[\033[30m\]'
FG_BLUE='\[\033[34m\]'
FG_GREEN='\[\033[32m\]'
FG_YELLOW='\[\033[33m\]'
FG_RED='\[\033[31m\]'
FG_PURPLE='\[\033[35m\]'
FG_CYAN='\[\033[36m\]'
FG_DARK_GRAY='\[\033[90m\]'

# Unicode elements (powerline-style)
# Check if terminal supports powerline fonts
if fc-list | grep -qi "powerline\|nerd"; then
    ARROW_RIGHT=''
    ARROW_LEFT=''
    BRANCH_SYMBOL='󰘬'
    FOLDER_SYMBOL=''
    PROMPT_SYMBOL='❯'
else
    # Fallback to ASCII characters
    ARROW_RIGHT='▶'
    ARROW_LEFT='◀'
    BRANCH_SYMBOL='⎇'
    FOLDER_SYMBOL='📁'
    PROMPT_SYMBOL='→'
fi

# Function to build the prompt
build_fancy_prompt() {
    local exit_code=$?
    PS1=""

    # Start with newline for breathing room
    PS1+="\n"

    # User section (green background)
    PS1+="${BG_GREEN}${FG_BLACK}${BOLD} \u ${RESET}"
    PS1+="${FG_GREEN}${BG_BLUE}${ARROW_RIGHT}${RESET}"

    # Host section (blue background)
    PS1+="${BG_BLUE}${FG_WHITE}${BOLD} \h ${RESET}"
    PS1+="${FG_BLUE}${BG_PURPLE}${ARROW_RIGHT}${RESET}"

    # Directory section (purple background)
    PS1+="${BG_PURPLE}${FG_WHITE}${BOLD} ${FOLDER_SYMBOL} \w ${RESET}"

    # Git section (if in git repo)
    if [ -n "$(__git_ps1 '%s')" ]; then
        local git_status=$(__git_ps1 '%s')
        local git_bg="${BG_CYAN}"
        local git_fg="${FG_BLACK}"

        # Change color based on git status
        if [[ $git_status == *"*"* ]] || [[ $git_status == *"+"* ]]; then
            git_bg="${BG_YELLOW}"
            git_fg="${FG_BLACK}"
        fi

        PS1+="${FG_PURPLE}${git_bg}${ARROW_RIGHT}${RESET}"
        PS1+="${git_bg}${git_fg}${BOLD} ${BRANCH_SYMBOL} ${git_status} ${RESET}"
        PS1+="${FG_CYAN}${ARROW_RIGHT}${RESET}"
    else
        PS1+="${FG_PURPLE}${ARROW_RIGHT}${RESET}"
    fi

    # Exit status indicator
    PS1+="\n"
    if [ $exit_code -eq 0 ]; then
        PS1+="${FG_GREEN}${PROMPT_SYMBOL}${RESET} "
    else
        PS1+="${FG_RED}${PROMPT_SYMBOL}${RESET} "
    fi
}

# Set PROMPT_COMMAND to build prompt dynamically
PROMPT_COMMAND='build_fancy_prompt'
EOF
fi

# Remove the old PS1 update since we're using PROMPT_COMMAND now
# (No need for the sed command anymore)

# Source bashrc to get aliases and git configuration
source "$HOME/.bashrc"

# Ensure the configuration is applied for the current session
export PATH="$HOME/.local/bin:$PATH"
export GIT_PS1_SHOWDIRTYSTATE=1
export GIT_PS1_SHOWSTASHSTATE=1
export GIT_PS1_SHOWUNTRACKEDFILES=1
export GIT_PS1_SHOWUPSTREAM="auto"
export GIT_PS1_SHOWCOLORHINTS=1
export GIT_PS1_DESCRIBE_STYLE="branch"

# Load git prompt if available
if [ -f /usr/lib/git-core/git-sh-prompt ]; then
    source /usr/lib/git-core/git-sh-prompt
fi

echo "Git prompt configuration applied successfully!"
