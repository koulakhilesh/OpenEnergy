#!/bin/bash

# Create virtual environment
python3 -m venv openenergy_env

# Activate virtual environment
source openenergy_env/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Platform-specific instructions
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "Installing glpk on macOS..."
    brew install glpk
    echo "For ipopt, follow the instructions from the Ipopt documentation: https://coin-or.github.io/Ipopt/INSTALL.html"
elif [[ "$OSTYPE" == "msys" ]]; then
    # Windows
    echo "Installing glpk on Windows..."
    choco install glpk
    echo "For ipopt, follow the instructions from the Ipopt documentation: https://coin-or.github.io/Ipopt/INSTALL.html"
else
    echo "Please install glpk and ipopt manually for your platform."
fi

echo "Virtual environment setup complete. To activate, run 'source openenergy_env/bin/activate'."
