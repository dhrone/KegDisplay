#!/bin/bash

# Script to set up GPIO permissions for the beer user
# This script can be run independently to fix GPIO access issues

set -e  # Exit immediately if a command exits with a non-zero status

# Function to output messages
log() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

# Function to output error messages
error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1" >&2
}

# Function to output success messages
success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

# Verify the script is run as root
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root"
    exit 1
fi

# Check if beer user exists
if ! id -u beer &>/dev/null; then
    error "Beer user does not exist. Please run the full installation script first."
    exit 1
fi

log "Setting up GPIO permissions for beer user..."

# Add beer user to gpio group if it exists
if getent group gpio > /dev/null; then
    usermod -a -G gpio beer || {
        error "Failed to add beer user to gpio group.";
        exit 1;
    }
    log "Added beer user to gpio group."
else
    log "gpio group not found. Creating gpio group and udev rules."
fi

# Create udev rules for GPIO access
log "Creating udev rules for GPIO access..."
cat > /etc/udev/rules.d/99-gpio.rules << 'EOF'
SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", KERNEL=="gpio*", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", KERNEL=="gpio*", RUN+="/bin/chgrp gpio /dev/gpio%n"
SUBSYSTEM=="gpio", KERNEL=="gpio*", RUN+="/bin/chmod g+rw /dev/gpio%n"
EOF

# Create gpio group if it doesn't exist
if ! getent group gpio > /dev/null; then
    groupadd gpio || {
        error "Failed to create gpio group.";
        exit 1;
    }
    usermod -a -G gpio beer || {
        error "Failed to add beer user to gpio group.";
        exit 1;
    }
    log "Created gpio group and added beer user to it."
fi

# Reload udev rules
log "Reloading udev rules..."
udevadm control --reload-rules || {
    error "Failed to reload udev rules.";
    exit 1;
}
udevadm trigger || {
    error "Failed to trigger udev rules.";
    exit 1;
}

# Set permissions on /dev/mem for direct memory access
log "Setting up permissions for /dev/mem access..."
cat > /etc/udev/rules.d/98-mem.rules << 'EOF'
SUBSYSTEM=="mem", KERNEL=="mem", GROUP="gpio", MODE="0660"
EOF

# Reload udev rules again to apply mem permissions
udevadm control --reload-rules || {
    error "Failed to reload udev rules.";
    exit 1;
}
udevadm trigger || {
    error "Failed to trigger udev rules.";
    exit 1;
}

# Set current permissions on /dev/mem
chgrp gpio /dev/mem || {
    error "Failed to change group of /dev/mem.";
    exit 1;
}
chmod g+rw /dev/mem || {
    error "Failed to change permissions of /dev/mem.";
    exit 1;
}

success "GPIO permissions have been set up successfully!"
log "The beer user now has access to GPIO devices."
log "You may need to log out and log back in for the group changes to take effect."
log "To test, run: sudo -u beer python3 -c 'import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM)'" 