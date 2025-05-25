#!/bin/bash

# KegDisplay Auto-Installation Script for DietPi
# This script installs KegDisplay as a primary system with web interface
# using fixed configuration values optimized for DietPi

set -e  # Exit immediately if a command exits with a non-zero status

# Fixed configuration values
INSTALL_TYPE="primary"
TAP_NUMBER="1"
DISPLAY_TYPE="ws0010"
INTERFACE_TYPE="pigpio"
INSTALL_TKINTER="false"
RS_PIN="7"
E_PIN="8"
DATA_PINS="25 5 6 12"

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
            # Install development dependencies if requested
            if [ "$INSTALL_TKINTER" = "true" ]; then
                log "Installing development dependencies..."
                sudo -u beer bash -c "cd $directory && /home/beer/.poetry/bin/poetry install --with dev" || {
                    error "Failed to install development dependencies.";
                    return 1;
                }
            fi
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
log "Welcome to the KegDisplay auto-installation script for DietPi."
log "This script will set up KegDisplay on your system with the following configuration:"
log "Installation Type: $INSTALL_TYPE"
log "Tap Number: $TAP_NUMBER"
log "Display Type: $DISPLAY_TYPE"
log "Interface Type: $INTERFACE_TYPE"
log "RS Pin: $RS_PIN"
log "E Pin: $E_PIN"
log "Data Pins: $DATA_PINS"

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
    gfortran libopenblas-dev liblapack-dev fonts-dejavu-core openssl || {
    error "Failed to install system dependencies.";
    exit 1;
}

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

# Clone the KegDisplayDB repository
log "Cloning KegDisplayDB repository..."
sudo -u beer mkdir -p /home/beer/Dev
cd /home/beer/Dev
if [ -d "KegDisplayDB" ]; then
    log "KegDisplayDB directory already exists, updating..."
    cd KegDisplayDB
    sudo -u beer git pull
else
    sudo -u beer git clone https://github.com/dhrone/KegDisplayDB || {
        error "Failed to clone KegDisplayDB repository.";
        exit 1;
    }
    cd KegDisplayDB
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
    log "Reinitializing database..."
    sudo -u beer bash -c "cd /home/beer/Dev/KegDisplay && /home/beer/.poetry/bin/poetry run python -m KegDisplay.db.createDB" || {
        error "Failed to initialize database.";
        exit 1;
    }
    log "Database reinitialized successfully."
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
sed -i "s|ExecStart=.*|ExecStart=/home/beer/.poetry/bin/poetry run python -m KegDisplay.taggstaps --tap $TAP_NUMBER --display $DISPLAY_TYPE --interface $INTERFACE_TYPE --RS $RS_PIN --E $E_PIN --PINS $DATA_PINS|" /etc/systemd/system/taggstaps.service || {
    error "Failed to update taggstaps.service configuration.";
    exit 1;
}

# Update the WorkingDirectory path in the service file
sed -i "s|WorkingDirectory=.*|WorkingDirectory=/home/beer/Dev/KegDisplay|" /etc/systemd/system/taggstaps.service || {
    error "Failed to update taggstaps.service WorkingDirectory.";
    exit 1;
}

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

# Enable and start webinterface service
systemctl enable webinterface.service || {
    error "Failed to enable webinterface service.";
    exit 1;
}
systemctl start webinterface.service || {
    error "Failed to start webinterface service.";
    exit 1;
}

# Generate SSL certificate for web interface
log "Generating SSL certificate for web interface..."
# Create directories if they don't exist
mkdir -p /etc/ssl/private
mkdir -p /etc/ssl/certs

# Set proper permissions on parent directories
chmod 750 /etc/ssl/private
chmod 755 /etc/ssl/certs
chown root:ssl-cert /etc/ssl/private

# Generate certificate and key
openssl req -x509 -newkey rsa:4096 -keyout /etc/ssl/private/kegdisplay.key -out /etc/ssl/certs/kegdisplay.crt -days 365 -nodes -subj "/CN=localhost" || {
    error "Failed to generate SSL certificate.";
    exit 1;
}

# Set proper ownership and permissions
chown root:root /etc/ssl/private/kegdisplay.key
chown root:root /etc/ssl/certs/kegdisplay.crt
chmod 640 /etc/ssl/private/kegdisplay.key
chmod 644 /etc/ssl/certs/kegdisplay.crt

# Create ssl-cert group if it doesn't exist and add beer user to it
if ! getent group ssl-cert > /dev/null; then
    groupadd ssl-cert || {
        error "Failed to create ssl-cert group.";
        exit 1;
    }
    log "Created ssl-cert group."
fi

usermod -a -G ssl-cert beer || {
    error "Failed to add beer user to ssl-cert group.";
    exit 1;
}
log "Added beer user to ssl-cert group."

chgrp ssl-cert /etc/ssl/private/kegdisplay.key

success "KegDisplay has been installed successfully!"
log "The web interface is available at http://$(hostname -I | awk '{print $1}'):8080"
log "To check the status of the services, run:"
log "  systemctl status taggstaps.service"
log "  systemctl status webinterface.service"
log "Log files are located in /var/log/KegDisplay/"
log "Thank you for installing KegDisplay!" 