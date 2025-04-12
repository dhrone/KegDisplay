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

# Function to handle Poetry installation with lock file recovery
install_poetry_dependencies() {
    local directory=$1
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log "Installing Python dependencies (attempt $attempt of $max_attempts)..."
        
        # Try to install dependencies
        if sudo -u beer bash -c "cd $directory && source /home/beer/.cargo/env && /home/beer/.poetry/bin/poetry install"; then
            success "Python dependencies installed successfully!"
            return 0
        fi
        
        # Check if the error is related to the lock file
        log "Checking lock file status..."
        if sudo -u beer bash -c "cd $directory && /home/beer/.poetry/bin/poetry lock" 2>&1 | grep -q "Lock file is out of date"; then
            log "Lock file is out of date. Updating lock file..."
            if sudo -u beer bash -c "cd $directory && /home/beer/.poetry/bin/poetry lock"; then
                log "Lock file updated successfully. Retrying installation..."
                attempt=$((attempt + 1))
                continue
            else
                error "Failed to update lock file."
                return 1
            fi
        else
            # If the error is not related to the lock file, don't retry
            error "Failed to install Python dependencies."
            return 1
        fi
    done
    
    error "Failed to install Python dependencies after $max_attempts attempts."
    return 1
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
while [ "$INTERFACE_TYPE" != "bitbang" ] && [ "$INTERFACE_TYPE" != "pigpio" ] && [ "$INTERFACE_TYPE" != "spi" ]; do
    read -p "What type of interface is being used? (bitbang/pigpio/spi): " INTERFACE_TYPE
    INTERFACE_TYPE=$(echo "$INTERFACE_TYPE" | tr '[:upper:]' '[:lower:]')
    if [ "$INTERFACE_TYPE" != "bitbang" ] && [ "$INTERFACE_TYPE" != "pigpio" ] && [ "$INTERFACE_TYPE" != "spi" ]; then
        error "Invalid choice. Please enter 'bitbang', 'pigpio', or 'spi'."
    fi
done

# Ask if tkinter is needed for testing
INSTALL_TKINTER=""
while [ "$INSTALL_TKINTER" != "y" ] && [ "$INSTALL_TKINTER" != "n" ]; do
    read -p "Do you need tkinter for testing? (y/n): " INSTALL_TKINTER
    INSTALL_TKINTER=$(echo "$INSTALL_TKINTER" | tr '[:upper:]' '[:lower:]')
    if [ "$INSTALL_TKINTER" != "y" ] && [ "$INSTALL_TKINTER" != "n" ]; then
        error "Invalid choice. Please enter 'y' or 'n'."
    fi
done

# Additional interface settings if using bitbang or pigpio
RS_PIN=""
E_PIN=""
DATA_PINS=""

if [ "$INTERFACE_TYPE" = "bitbang" ] || [ "$INTERFACE_TYPE" = "pigpio" ]; then
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
    libjpeg-dev zlib1g-dev libfreetype6-dev python3-pip logrotate libffi-dev \
    build-essential python3-venv python3-distutils python3-setuptools \
    libssl-dev libncurses5-dev libsqlite3-dev libreadline-dev \
    libgdbm-dev libdb5.3-dev libbz2-dev libexpat1-dev liblzma-dev \
    gfortran libopenblas-dev liblapack-dev || {
    error "Failed to install system dependencies.";
    exit 1;
}

# Install pigpio if using pigpio interface
if [ "$INTERFACE_TYPE" = "pigpio" ]; then
    log "Installing pigpio for pigpio interface..."
    apt-get install -y pigpio python3-pigpio || {
        error "Failed to install pigpio.";
        exit 1;
    }

    # Configure pigpio daemon
    log "Configuring pigpio daemon..."
    # Create systemd service file for pigpiod
    cat > /etc/systemd/system/pigpiod.service << 'EOF'
[Unit]
Description=pigpio daemon
After=network.target

[Service]
ExecStart=/usr/bin/pigpiod -l
Type=forking
PIDFile=/run/pigpio.pid
ExecStop=/bin/systemctl kill -s SIGKILL pigpiod

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start pigpiod service
    systemctl daemon-reload
    systemctl enable pigpiod || {
        error "Failed to enable pigpiod service.";
        exit 1;
    }
    systemctl start pigpiod || {
        error "Failed to start pigpiod service.";
        exit 1;
    }

    # Ensure pigpio socket has correct permissions
    chmod 666 /var/run/pigpio.sock || {
        log "Note: pigpio socket permissions could not be set. This might be because the service hasn't created it yet.";
    }
fi

# Install tkinter if requested
if [ "$INSTALL_TKINTER" = "y" ]; then
    log "Installing tkinter..."
    apt-get install -y python3-tk || {
        error "Failed to install tkinter.";
        exit 1;
    }
fi

# Create beer user account
log "Creating beer user account..."
id -u beer &>/dev/null || useradd -m -s /bin/bash beer || {
    error "Failed to create beer user account.";
    exit 1;
}

# Set up GPIO permissions
log "Setting up GPIO permissions..."
# Add beer user to gpio group if it exists
if getent group gpio > /dev/null; then
    usermod -a -G gpio beer || {
        error "Failed to add beer user to gpio group.";
        exit 1;
    }
    log "Added beer user to gpio group."
else
    log "gpio group not found. Creating udev rules for GPIO access."
fi

# Add beer user to spi group
if getent group spi > /dev/null; then
    usermod -a -G spi beer || {
        error "Failed to add beer user to spi group.";
        exit 1;
    }
    log "Added beer user to spi group."
else
    log "spi group not found. Creating udev rules for SPI access."
    # Create spi group if it doesn't exist
    groupadd spi || {
        error "Failed to create spi group.";
        exit 1;
    }
    usermod -a -G spi beer || {
        error "Failed to add beer user to spi group.";
        exit 1;
    }
    log "Created spi group and added beer user to it."
fi

# Create udev rules for GPIO access
log "Creating udev rules for GPIO access..."
cat > /etc/udev/rules.d/99-gpio.rules << 'EOF'
SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", KERNEL=="gpio*", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpio", KERNEL=="gpio*", RUN+="/bin/chgrp gpio /dev/gpio%n"
SUBSYSTEM=="gpio", KERNEL=="gpio*", RUN+="/bin/chmod g+rw /dev/gpio%n"
EOF

# Create udev rules for SPI access
log "Creating udev rules for SPI access..."
cat > /etc/udev/rules.d/99-spi.rules << 'EOF'
SUBSYSTEM=="spidev", GROUP="spi", MODE="0660"
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
udevadm control --reload-rules || {
    error "Failed to reload udev rules.";
    exit 1;
}
udevadm trigger || {
    error "Failed to trigger udev rules.";
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

# Install Rust for the beer user
log "Installing Rust for beer user..."
sudo -u beer bash -c "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y" || {
    error "Failed to install Rust for beer user.";
    exit 1;
}

# Source Rust environment
if ! sudo -u beer bash -c "source /home/beer/.cargo/env"; then
    error "Failed to source Rust environment.";
    exit 1;
fi

# Install Poetry
log "Installing Poetry..."
sudo -u beer bash -c "curl -sSL https://install.python-poetry.org | POETRY_HOME=/home/beer/.poetry python3 -" || {
    error "Failed to install Poetry.";
    exit 1;
}

# Add Poetry bin directory to PATH for beer user
echo 'export PATH="/home/beer/.poetry/bin:$PATH"' >> /home/beer/.bashrc

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
if ! install_poetry_dependencies "/home/beer/Dev/KegDisplay"; then
    error "Failed to install Python dependencies. Installation aborted."
    exit 1
fi

# Initialize the database
log "Initializing the database..."
sudo -u beer bash -c "cd /home/beer/Dev/KegDisplay && mkdir -p KegDisplay" || {
    error "Failed to create KegDisplay directory.";
    exit 1;
}

# Check if the database already exists
if [ -f "/home/beer/Dev/KegDisplay/KegDisplay/beer.db" ]; then
    log "Database already exists at /home/beer/Dev/KegDisplay/KegDisplay/beer.db"
    read -p "Do you want to reinitialize the database? This will overwrite the existing database. (y/n): " REINIT_DB
    REINIT_DB=$(echo "$REINIT_DB" | tr '[:upper:]' '[:lower:]')
    if [ "$REINIT_DB" != "y" ]; then
        log "Skipping database initialization. Using existing database."
    else
        # Initialize the database using the repository's create script
        log "Reinitializing database..."
        sudo -u beer bash -c "cd /home/beer/Dev/KegDisplay && /home/beer/.poetry/bin/poetry run python -m KegDisplay.db.createDB" || {
            error "Failed to initialize database.";
            exit 1;
        }
        log "Database reinitialized successfully."
    fi
else
    # Initialize the database using the repository's create script
    log "Initializing database..."
    sudo -u beer bash -c "cd /home/beer/Dev/KegDisplay && /home/beer/.poetry/bin/poetry run python -m KegDisplay.db.createDB" || {
        error "Failed to initialize database.";
        exit 1;
    }
    log "Database initialized successfully."
fi

# Verify the database was created in the correct location
if [ ! -f "/home/beer/Dev/KegDisplay/KegDisplay/beer.db" ]; then
    error "Database was not created in the expected location. Please check the application logs for more information.";
    exit 1;
fi

log "Database initialization completed."

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
sed -i "s|ExecStart=.*|ExecStart=/home/beer/.local/bin/poetry run python -m KegDisplay.taggstaps --tap $TAP_NUMBER --display $DISPLAY_TYPE --interface $INTERFACE_TYPE$([ "$INTERFACE_TYPE" = "bitbang" ] || [ "$INTERFACE_TYPE" = "pigpio" ] && echo " --RS $RS_PIN --E $E_PIN --PINS $DATA_PINS")|" /etc/systemd/system/taggstaps.service || {
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