#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Install Chrome for Selenium
# Use the newer method for adding repository keys
curl -sS -o /tmp/google-chrome.key https://dl-ssl.google.com/linux/linux_signing_key.pub
install -D /tmp/google-chrome.key /etc/apt/keyrings/google-chrome.key
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.key] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Update and install Chrome
apt-get -y update
apt-get -y install google-chrome-stable

# Install ChromeDriver
# First try to get the version matching the installed Chrome
CHROME_VERSION=$(google-chrome-stable --version | awk '{print $3}' | cut -d. -f1)
CHROME_DRIVER_VERSION=$(curl -sS "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}" || curl -sS "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")

# Download and install ChromeDriver
echo "Installing ChromeDriver version: $CHROME_DRIVER_VERSION"
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip"
unzip /tmp/chromedriver.zip -d /usr/local/bin/
chmod +x /usr/local/bin/chromedriver

# Verify installation
chromedriver --version
google-chrome-stable --version