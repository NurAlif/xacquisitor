#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate 2>/dev/null

clear
echo -e "\033[94mXacquisitor Restricted Shell\033[0m"
echo -e "\033[93m▸ To start the pipeline, run:\033[0m \033[1;92mpython3 run.py\033[0m"
echo -e "\033[90mAllowed commands: python3 <file.py>, clear, ls, cat, exit\033[0m\n"

while true; do
    read -e -p "xacquisitor> " cmd
    
    # Ignore empty commands
    if [ -z "$cmd" ]; then
        continue
    fi
    
    # Keep history
    history -s "$cmd"
    
    # Simple validation allowing python3 calls with arguments, clear, ls, cat, exit
    if [[ "$cmd" == python3\ *.py* ]] || [[ "$cmd" == python\ *.py* ]] || [[ "$cmd" == ./venv/bin/python\ *.py* ]]; then
        eval "$cmd"
    elif [[ "$cmd" == "clear" ]]; then
        clear
    elif [[ "$cmd" == "ls" ]] || [[ "$cmd" == ls\ * ]]; then
        eval "$cmd"
    elif [[ "$cmd" == "cat" ]] || [[ "$cmd" == cat\ * ]]; then
        eval "$cmd"
    elif [[ "$cmd" == "exit" || "$cmd" == "quit" ]]; then
        echo "Exiting..."
        exit 0
    else
        echo -e "\033[91m⚠ Only Python scripts (.py) and basic commands are allowed.\033[0m"
    fi
done
