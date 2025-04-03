#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Install Chrome for Selenium - using a more direct approach
echo "Installing Google Chrome..."

# Install dependencies
apt-get update
apt-get install -y wget gnupg2 apt-utils

# Add Google Chrome repository
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Update and install Chrome
apt-get update
apt-get install -y google-chrome-stable

# Verify Chrome installation
which google-chrome-stable
ls -la /usr/bin/google-chrome-stable
google-chrome-stable --version

# Install ChromeDriver
echo "Installing ChromeDriver..."

# Install unzip if not already installed
apt-get install -y unzip

# Get Chrome version
CHROME_VERSION=$(google-chrome-stable --version | awk '{print $3}' | cut -d. -f1)
echo "Chrome version: $CHROME_VERSION"

# Try to get matching ChromeDriver version
CHROME_DRIVER_VERSION=$(curl -sS "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}")

# If that fails, get the latest version
if [ -z "$CHROME_DRIVER_VERSION" ]; then
    echo "Could not find ChromeDriver for Chrome version $CHROME_VERSION, using latest"
    CHROME_DRIVER_VERSION=$(curl -sS "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
fi

echo "Installing ChromeDriver version: $CHROME_DRIVER_VERSION"

# Download and install ChromeDriver
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip"
unzip /tmp/chromedriver.zip -d /usr/local/bin/
chmod +x /usr/local/bin/chromedriver

# Create symlink to ensure it's in PATH
ln -sf /usr/local/bin/chromedriver /usr/bin/chromedriver

# Verify installation
echo "ChromeDriver location:"
which chromedriver
ls -la /usr/local/bin/chromedriver
ls -la /usr/bin/chromedriver
echo "ChromeDriver version:"
chromedriver --version

# Final verification
echo "Final verification of Chrome and ChromeDriver:"
google-chrome-stable --version
chromedriver --version