#!/usr/bin/env bash
# exit on error
set -o errexit

# Print all commands for debugging
set -x

# Install Python dependencies
pip install -r requirements.txt

# Create directories for Chrome and ChromeDriver
mkdir -p /opt/chrome
mkdir -p /opt/chromedriver

# Install system dependencies
apt-get update
apt-get install -y wget unzip xvfb libxi6 libgconf-2-4 fonts-liberation

# Download and install Chrome
echo "Downloading Chrome..."
wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
echo "Installing Chrome..."
dpkg -i /tmp/chrome.deb || apt-get install -yf
rm /tmp/chrome.deb

# Verify Chrome installation
echo "Verifying Chrome installation..."
ls -la /usr/bin/google-chrome-stable || echo "Chrome not found in /usr/bin"
which google-chrome-stable || echo "Chrome not in PATH"
google-chrome-stable --version || echo "Failed to get Chrome version"

# Create a symbolic link to make sure Chrome is in a standard location
ln -sf /usr/bin/google-chrome-stable /opt/chrome/chrome
chmod +x /opt/chrome/chrome
ls -la /opt/chrome/chrome

# Download and install ChromeDriver
echo "Downloading ChromeDriver..."
CHROME_VERSION=$(google-chrome-stable --version | grep -oP '\d+\.\d+\.\d+' | cut -d. -f1)
echo "Chrome major version: $CHROME_VERSION"

# Get the matching ChromeDriver version
CHROME_DRIVER_VERSION=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION")
echo "ChromeDriver version: $CHROME_DRIVER_VERSION"

# If we couldn't get a matching version, try the latest
if [ -z "$CHROME_DRIVER_VERSION" ]; then
    echo "Could not find matching ChromeDriver, using latest"
    CHROME_DRIVER_VERSION=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
    echo "Latest ChromeDriver version: $CHROME_DRIVER_VERSION"
fi

# Download and install ChromeDriver
wget -q -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip"
unzip -q /tmp/chromedriver.zip -d /opt/chromedriver
rm /tmp/chromedriver.zip
chmod +x /opt/chromedriver/chromedriver

# Create symbolic links to make sure ChromeDriver is in standard locations
ln -sf /opt/chromedriver/chromedriver /usr/bin/chromedriver
ln -sf /opt/chromedriver/chromedriver /usr/local/bin/chromedriver

# Verify ChromeDriver installation
echo "Verifying ChromeDriver installation..."
ls -la /opt/chromedriver/chromedriver
ls -la /usr/bin/chromedriver
ls -la /usr/local/bin/chromedriver
which chromedriver || echo "ChromeDriver not in PATH"
chromedriver --version || echo "Failed to get ChromeDriver version"

# Create a file with Chrome and ChromeDriver paths for the app to read
echo "Creating paths file..."
echo "CHROME_PATH=/opt/chrome/chrome" > /etc/chrome-paths
echo "CHROMEDRIVER_PATH=/opt/chromedriver/chromedriver" >> /etc/chrome-paths
cat /etc/chrome-paths

# Final verification
echo "Final verification:"
google-chrome-stable --version
chromedriver --version

echo "Build script completed successfully"