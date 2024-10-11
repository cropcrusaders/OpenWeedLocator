#!/bin/bash

# Hailo 8 requirements installation script for Raspberry Pi 5
# Adapted for the Hailo 8 AI acceleration module

set -e  # Exit immediately if a command exits with a non-zero status

# Update and upgrade existing packages
sudo apt-get update && sudo apt-get upgrade -y

# Install prerequisites
sudo apt-get install -y cmake curl gnupg lsb-release build-essential python3-venv python3-pip libssl-dev libffi-dev git

# Add Hailo repository key and list
curl https://repository.hailo.ai/apt/hailo-archive-keyring.gpg | sudo gpg --dearmor -o /usr/share/keyrings/hailo-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/hailo-archive-keyring.gpg] https://repository.hailo.ai/apt/ default main" | sudo tee /etc/apt/sources.list.d/hailo.list > /dev/null

# Update package lists
sudo apt-get update

# Install Hailo driver and SDK
sudo apt-get install -y hailort-dkms hailort-cli hailort-runtime hailort-python3

# Prompt user to connect the Hailo 8 device
while true; do
    read -r -p "Please connect the Hailo 8 AI acceleration module to the Raspberry Pi 5. Press [y] then enter to continue: " response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])+$ ]]; then
        break
    else
        echo "Invalid response. Please try again."
    fi
done

# Validate the installation
echo "Validating Hailo installation..."
hailort-cli info || { echo "Error: Hailo installation validation failed."; exit 1; }

# Set up virtual environment for the OWL project
VENV_DIR="$HOME/owl_venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating a Python virtual environment for the OWL project..."
    python3 -m venv "$VENV_DIR"
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip and install required Python packages
pip install --upgrade pip
pip install wheel setuptools

# Install hailort in the OWL virtual environment
pip install hailort

# Install additional Python dependencies
echo "Installing additional Python dependencies..."
REQUIREMENTS_FILE="requirements.txt"

if [ -f "$REQUIREMENTS_FILE" ]; then
    pip install -r "$REQUIREMENTS_FILE"
else
    echo "Warning: requirements.txt not found. Skipping additional Python dependencies installation."
fi

# Clone OWL repository if not already present
OWL_REPO_DIR="$HOME/owl"
if [ ! -d "$OWL_REPO_DIR" ]; then
    echo "Cloning OWL repository..."
    git clone https://github.com/YourOrganization/OpenWeedLocator.git "$OWL_REPO_DIR"
fi

# Finalizing setup
echo "Linking Hailo libraries to the virtual environment..."
HAILO_LIB_DIRS=$(find /usr/lib -name "*hailort*" -type d)

if [ -z "$HAILO_LIB_DIRS" ]; then
    echo "Error: Could not find Hailo library directories. Installation may have failed."
    exit 1
fi

# Link Hailo libraries to the virtual environment
for DIR in $HAILO_LIB_DIRS; do
    ln -sf "$DIR" "$VENV_DIR/lib/python3.*/site-packages/"
done

# Add udev rules for Hailo 8
echo "Adding udev rules for Hailo 8 device..."
RULES_FILE="/etc/udev/rules.d/99-hailo.rules"
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="1fc9", ATTR{idProduct}=="0021", MODE="0666"' | sudo tee "$RULES_FILE" > /dev/null
sudo udevadm control --reload-rules && sudo udevadm trigger

# Reboot suggestion
echo "Installation and setup complete. It is recommended to reboot your Raspberry Pi for all changes to take effect."
