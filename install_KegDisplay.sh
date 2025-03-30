#!/bin/bash

# KegDisplay Installation Script
# This script installs KegDisplay either as a primary system with web interface
# or as a secondary system with database sync client.

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

# Welcome message
log "Welcome to the KegDisplay installation script."
log "This script will set up KegDisplay on your system."

# Determine installation type
INSTALL_TYPE=""
while [ "$INSTALL_TYPE" != "primary" ] && [ "$INSTALL_TYPE" != "secondary" ]; do
    read -p "Is this a primary (with web interface) or secondary installation? (primary/secondary): " INSTALL_TYPE
    INSTALL_TYPE=$(echo "$INSTALL_TYPE" | tr '[:upper:]' '[:lower:]')
    if [ "$INSTALL_TYPE" != "primary" ] && [ "$INSTALL_TYPE" != "secondary" ]; then
        error "Invalid choice. Please enter 'primary' or 'secondary'."
    fi
done

# Get the tap number for this installation
TAP_NUMBER=""
while ! [[ "$TAP_NUMBER" =~ ^[0-9]+$ ]]; do
    read -p "What tap number will this installation use? (1-99): " TAP_NUMBER
    if ! [[ "$TAP_NUMBER" =~ ^[0-9]+$ ]] || [ "$TAP_NUMBER" -lt 1 ] || [ "$TAP_NUMBER" -gt 99 ]; then
        error "Please enter a valid tap number between 1 and 99."
    fi
done

# Get display type
DISPLAY_TYPE=""
while [ "$DISPLAY_TYPE" != "ws0010" ] && [ "$DISPLAY_TYPE" != "ssd1322" ]; do
    read -p "What type of display is connected? (ws0010/ssd1322): " DISPLAY_TYPE
    DISPLAY_TYPE=$(echo "$DISPLAY_TYPE" | tr '[:upper:]' '[:lower:]')
    if [ "$DISPLAY_TYPE" != "ws0010" ] && [ "$DISPLAY_TYPE" != "ssd1322" ]; then
        error "Invalid choice. Please enter 'ws0010' or 'ssd1322'."
    fi
done

# Get interface type
INTERFACE_TYPE=""
while [ "$INTERFACE_TYPE" != "bitbang" ] && [ "$INTERFACE_TYPE" != "spi" ]; do
    read -p "What type of interface is being used? (bitbang/spi): " INTERFACE_TYPE
    INTERFACE_TYPE=$(echo "$INTERFACE_TYPE" | tr '[:upper:]' '[:lower:]')
    if [ "$INTERFACE_TYPE" != "bitbang" ] && [ "$INTERFACE_TYPE" != "spi" ]; then
        error "Invalid choice. Please enter 'bitbang' or 'spi'."
    fi
done

# Additional interface settings if using bitbang
RS_PIN=""
E_PIN=""
DATA_PINS=""

if [ "$INTERFACE_TYPE" = "bitbang" ]; then
    # Get RS pin
    while ! [[ "$RS_PIN" =~ ^[0-9]+$ ]]; do
        read -p "Enter the RS pin number: " RS_PIN
        if ! [[ "$RS_PIN" =~ ^[0-9]+$ ]]; then
            error "Please enter a valid pin number."
        fi
    done
    
    # Get E pin
    while ! [[ "$E_PIN" =~ ^[0-9]+$ ]]; do
        read -p "Enter the E pin number: " E_PIN
        if ! [[ "$E_PIN" =~ ^[0-9]+$ ]]; then
            error "Please enter a valid pin number."
        fi
    done
    
    # Get data pins
    while true; do
        read -p "Enter the data pins (space-separated, e.g., '25 5 6 12'): " DATA_PINS
        # Check if each entered pin is a number
        valid=true
        for pin in $DATA_PINS; do
            if ! [[ "$pin" =~ ^[0-9]+$ ]]; then
                valid=false
                break
            fi
        done
        
        if [ "$valid" = true ] && [ -n "$DATA_PINS" ]; then
            break
        else
            error "Please enter valid pin numbers separated by spaces."
        fi
    done
fi

# Begin installation
log "Beginning system installation..."

# Update package lists
log "Updating package lists..."
apt-get update || { error "Failed to update package lists."; exit 1; }

# Install system dependencies
log "Installing system dependencies..."
apt-get install -y python3 git gcc vim-tiny sqlite3 python3-dev python3-rpi.gpio python3-spidev \
    libjpeg-dev zlib1g-dev libfreetype6-dev python3-pip logrotate || {
    error "Failed to install system dependencies.";
    exit 1;
}

# Create beer user account
log "Creating beer user account..."
id -u beer &>/dev/null || useradd -m -s /bin/bash beer || {
    error "Failed to create beer user account.";
    exit 1;
}

# Create log directory
log "Creating log directory..."
mkdir -p /var/log/KegDisplay || {
    error "Failed to create log directory.";
    exit 1;
}

# Set permissions on log directory
log "Setting permissions on log directory..."
chown -R beer:beer /var/log/KegDisplay || {
    error "Failed to set permissions on log directory.";
    exit 1;
}
chmod 755 /var/log/KegDisplay || {
    error "Failed to set permissions on log directory.";
    exit 1;
}

# Set up log rotation
log "Setting up log rotation..."
cat > /etc/logrotate.d/kegdisplay << 'EOF'
/var/log/KegDisplay/*.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0644 beer beer
}
EOF

# Install Poetry
log "Installing Poetry..."
sudo -u beer bash -c "curl -sSL https://install.python-poetry.org | python3 -" || {
    error "Failed to install Poetry.";
    exit 1;
}

# Add Poetry bin directory to PATH for beer user
echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/beer/.bashrc

# Clone the KegDisplay repository
log "Cloning KegDisplay repository..."
sudo -u beer mkdir -p /home/beer/Dev
cd /home/beer/Dev
if [ -d "KegDisplay" ]; then
    log "KegDisplay directory already exists, updating..."
    cd KegDisplay
    sudo -u beer git pull
else
    sudo -u beer git clone https://github.com/dhrone/KegDisplay || {
        error "Failed to clone KegDisplay repository.";
        exit 1;
    }
    cd KegDisplay
fi

# Install Python dependencies using Poetry
log "Installing Python dependencies..."
sudo -u beer bash -c "cd /home/beer/Dev/KegDisplay && $HOME/.local/bin/poetry install" || {
    error "Failed to install Python dependencies.";
    exit 1;
}

# Initialize the database
log "Initializing the database..."
sudo -u beer bash -c "cd /home/beer/Dev/KegDisplay && mkdir -p KegDisplay" || {
    error "Failed to create KegDisplay directory.";
    exit 1;
}

# Initialize the database using the repository's create script
log "Initializing database..."
sudo -u beer bash -c "cd /home/beer/Dev/KegDisplay && $HOME/.local/bin/poetry run python -m KegDisplay.db.createDB" || {
    error "Failed to initialize database.";
    exit 1;
}

# Create systemd service files
log "Creating systemd service files..."

# Install taggstaps service file
log "Installing taggstaps service..."
cp /home/beer/Dev/KegDisplay/taggstaps.service /etc/systemd/system/ || {
    error "Failed to copy taggstaps.service file.";
    exit 1;
}

# Customize the taggstaps service file with the correct parameters
log "Customizing taggstaps service configuration..."
# Use sed to modify the service file with the appropriate command
sed -i "s|ExecStart=.*|ExecStart=/home/beer/.local/bin/poetry run python -m KegDisplay.taggstaps --tap $TAP_NUMBER --display $DISPLAY_TYPE --interface $INTERFACE_TYPE$([ "$INTERFACE_TYPE" = "bitbang" ] && echo " --RS $RS_PIN --E $E_PIN --PINS $DATA_PINS")|" /etc/systemd/system/taggstaps.service || {
    error "Failed to update taggstaps.service configuration.";
    exit 1;
}

# Update the WorkingDirectory path in the service file
sed -i "s|WorkingDirectory=.*|WorkingDirectory=/home/beer/Dev/KegDisplay|" /etc/systemd/system/taggstaps.service || {
    error "Failed to update taggstaps.service WorkingDirectory.";
    exit 1;
}

# Create appropriate service file based on installation type
if [ "$INSTALL_TYPE" = "primary" ]; then
    # Install webinterface service file
    log "Installing webinterface service..."
    cp /home/beer/Dev/KegDisplay/webinterface.service /etc/systemd/system/ || {
        error "Failed to copy webinterface.service file.";
        exit 1;
    }
    
    # Update the WorkingDirectory path in the service file
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=/home/beer/Dev/KegDisplay|" /etc/systemd/system/webinterface.service || {
        error "Failed to update webinterface.service WorkingDirectory.";
        exit 1;
    }
else
    # Install dbsync_service service file for secondary systems
    log "Installing dbsync_service..."
    cp /home/beer/Dev/KegDisplay/dbsync_service.service /etc/systemd/system/ || {
        error "Failed to copy dbsync_service.service file.";
        exit 1;
    }
    
    # Update the WorkingDirectory path in the service file
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=/home/beer/Dev/KegDisplay|" /etc/systemd/system/dbsync_service.service || {
        error "Failed to update dbsync_service.service WorkingDirectory.";
        exit 1;
    }
    
    # Update the ExecStart command to use client mode
    sed -i "s|ExecStart=.*|ExecStart=/home/beer/.local/bin/poetry run python -m KegDisplay.dbsync_service --mode client|" /etc/systemd/system/dbsync_service.service || {
        error "Failed to update dbsync_service.service configuration.";
        exit 1;
    }
fi

# Start and enable services
log "Enabling and starting services..."
systemctl daemon-reload || {
    error "Failed to reload systemd daemon.";
    exit 1;
}

# Enable and start taggstaps service
systemctl enable taggstaps.service || {
    error "Failed to enable taggstaps service.";
    exit 1;
}
systemctl start taggstaps.service || {
    error "Failed to start taggstaps service.";
    exit 1;
}

# Enable and start appropriate service based on installation type
if [ "$INSTALL_TYPE" = "primary" ]; then
    systemctl enable webinterface.service || {
        error "Failed to enable webinterface service.";
        exit 1;
    }
    systemctl start webinterface.service || {
        error "Failed to start webinterface service.";
        exit 1;
    }
    success "KegDisplay primary system has been installed successfully!"
    log "The web interface is available at http://$(hostname -I | awk '{print $1}'):8080"
else
    systemctl enable dbsync_service.service || {
        error "Failed to enable dbsync_service service.";
        exit 1;
    }
    systemctl start dbsync_service.service || {
        error "Failed to start dbsync_service service.";
        exit 1;
    }
    success "KegDisplay secondary system has been installed successfully!"
fi

# Display final instructions
log "Installation complete!"
log "To check the status of the services, run:"
log "  systemctl status taggstaps.service"
if [ "$INSTALL_TYPE" = "primary" ]; then
    log "  systemctl status webinterface.service"
else
    log "  systemctl status dbsync_service.service"
fi
log "Log files are located in /var/log/KegDisplay/"
log "Thank you for installing KegDisplay!" 