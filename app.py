from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import concurrent.futures
import atexit
import os
import subprocess
import requests
from bs4 import BeautifulSoup
import time
import json

app = Flask(__name__)

CORS(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

def cleanup():
    executor.shutdown(wait=False)

atexit.register(cleanup)

def create_driver():
    print("Starting Chrome driver creation...")

    # Set up Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    # Try to read Chrome and ChromeDriver paths from the file created by build.sh
    chrome_path = None
    chromedriver_path = None

    try:
        if os.path.exists('/etc/chrome-paths'):
            print("Reading Chrome paths from /etc/chrome-paths")
            with open('/etc/chrome-paths', 'r') as f:
                for line in f:
                    if line.startswith('CHROME_PATH='):
                        chrome_path = line.strip().split('=')[1]
                    elif line.startswith('CHROMEDRIVER_PATH='):
                        chromedriver_path = line.strip().split('=')[1]

            print(f"Found Chrome path: {chrome_path}")
            print(f"Found ChromeDriver path: {chromedriver_path}")
    except Exception as e:
        print(f"Error reading Chrome paths file: {str(e)}")

    # If we couldn't read from the file, try standard locations
    if not chrome_path:
        possible_chrome_paths = [
            "/opt/chrome/chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/local/bin/google-chrome",
            "/opt/google/chrome/google-chrome"
        ]

        for path in possible_chrome_paths:
            if os.path.exists(path):
                chrome_path = path
                print(f"Found Chrome binary at: {chrome_path}")
                break

    if not chromedriver_path:
        possible_driver_paths = [
            "/opt/chromedriver/chromedriver",
            "/usr/local/bin/chromedriver",
            "/usr/bin/chromedriver"
        ]

        for path in possible_driver_paths:
            if os.path.exists(path):
                chromedriver_path = path
                print(f"Found ChromeDriver at: {chromedriver_path}")
                break

    # If we still don't have Chrome, try using 'which'
    if not chrome_path:
        try:
            result = subprocess.run(['which', 'google-chrome-stable'], capture_output=True, text=True)
            if result.stdout.strip():
                chrome_path = result.stdout.strip()
                print(f"Found Chrome using 'which' command at: {chrome_path}")
        except Exception as e:
            print(f"Error finding Chrome with 'which' command: {str(e)}")

    # If we still don't have ChromeDriver, try using 'which'
    if not chromedriver_path:
        try:
            result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True)
            if result.stdout.strip():
                chromedriver_path = result.stdout.strip()
                print(f"Found ChromeDriver using 'which' command at: {chromedriver_path}")
        except Exception as e:
            print(f"Error finding ChromeDriver with 'which' command: {str(e)}")

    # Set Chrome binary location if found
    if chrome_path:
        print(f"Setting Chrome binary location to: {chrome_path}")
        options.binary_location = chrome_path

    # Create the driver
    try:
        if chromedriver_path:
            print(f"Creating Chrome driver with explicit ChromeDriver path: {chromedriver_path}")
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            print("Successfully created Chrome driver with explicit ChromeDriver path")
            return driver
        else:
            print("No ChromeDriver path found, trying with ChromeDriverManager")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            print("Successfully created Chrome driver with ChromeDriverManager")
            return driver
    except Exception as e:
        print(f"Error creating Chrome driver: {str(e)}")

        # Try one more time with direct instantiation
        try:
            print("Trying direct Chrome instantiation")
            driver = webdriver.Chrome(options=options)
            print("Successfully created Chrome driver directly")
            return driver
        except Exception as e2:
            print(f"All methods failed. Final error: {str(e2)}")
            raise Exception(f"Failed to create Chrome driver after multiple attempts: {str(e2)}")

def scrape_data(driver, username, password):
    try:
        driver.get("http://mitsims.in/")
        StudentLink = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//nav//a[@id='studentLink']"))
        )
        StudentLink.click()

        userEle = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//form[@id='studentForm']//input[@id='inputStuId']"))
        )
        userEle.send_keys(username)

        passEle = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//form[@id='studentForm']//input[@id='inputPassword']"))
        )
        passEle.send_keys(password)

        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//form[@id='studentForm']//button[@id='studentSubmitButton']"))
        )
        login_button.click()

        attendance_percentage_xpath = "//fieldset[contains(@class, 'bottom-border') and not(contains(@class, 'bottom-border-header'))]//div[contains(@class,'x-column-inner')]/div[contains(@class,'x-field')][5]//span"
        course_name_xpath = "//fieldset[contains(@class, 'bottom-border') and not(contains(@class, 'bottom-border-header'))]//div[contains(@class,'x-column-inner')]/div[contains(@class,'x-field')][2]//span"

        attandance_percentages = []
        course_names = []

        wait = WebDriverWait(driver, 10)
        percentage_elements = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, attendance_percentage_xpath)))
        course_elements = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, course_name_xpath)))

        for element in percentage_elements:
            text_content = element.text.strip()
            try:
                percent_val = float(text_content)
                attandance_percentages.append(percent_val)
            except ValueError:
                attandance_percentages.append(0)

        for element in course_elements:
            course_names.append(element.text.strip())

        if not attandance_percentages:
            return None

        final_percent = round(sum(attandance_percentages) / len(attandance_percentages), 2)
        return {
            'courses': course_names,
            'percentages': attandance_percentages,
            'attendance': final_percent
        }
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
        return None
    finally:
        driver.quit()

# Fallback scraping function using requests and BeautifulSoup
def scrape_data_with_requests(username, password):
    print("Attempting to scrape data using requests and BeautifulSoup...")
    try:
        # Create a session to maintain cookies
        session = requests.Session()

        # Get the login page
        print("Getting login page...")
        response = session.get("http://mitsims.in/")
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the student login link and get its URL
        student_link = soup.find('a', id='studentLink')
        if not student_link:
            print("Could not find student login link")
            return None

        # Click on the student link
        print("Clicking on student link...")
        response = session.get("http://mitsims.in/" + student_link['href'])

        # Submit the login form
        print("Submitting login form...")
        login_data = {
            'inputStuId': username,
            'inputPassword': password
        }
        response = session.post("http://mitsims.in/student/login", data=login_data)

        # Check if login was successful
        if "Invalid" in response.text or "incorrect" in response.text.lower():
            print("Login failed")
            return None

        # Get the attendance data page
        print("Getting attendance data...")
        response = session.get("http://mitsims.in/student/attendance")
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract attendance data
        attendance_percentages = []
        course_names = []

        # This is a simplified extraction - you may need to adjust based on the actual HTML structure
        attendance_tables = soup.find_all('table', class_='attendance-table')
        for table in attendance_tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header row
                cells = row.find_all('td')
                if len(cells) >= 2:
                    course = cells[0].text.strip()
                    percentage_text = cells[1].text.strip().replace('%', '')
                    try:
                        percentage = float(percentage_text)
                        course_names.append(course)
                        attendance_percentages.append(percentage)
                    except ValueError:
                        pass

        if not attendance_percentages:
            print("No attendance data found")
            return None

        # Calculate final percentage
        final_percent = round(sum(attendance_percentages) / len(attendance_percentages), 2)

        return {
            'courses': course_names,
            'percentages': attendance_percentages,
            'attendance': final_percent
        }
    except Exception as e:
        print(f"Error in requests-based scraping: {str(e)}")
        return None

def get_attendance_data(username, password):
    # First try with Selenium
    try:
        print("Attempting to scrape with Selenium...")
        future = executor.submit(lambda: scrape_data(create_driver(), username, password))
        result = future.result(timeout=60)  # 1 minute timeout
        if result is not None:
            print("Successfully scraped data with Selenium")
            return result
    except concurrent.futures.TimeoutError:
        print("Selenium scraping operation timed out")
    except Exception as e:
        print(f"Error in Selenium scraping: {str(e)}")

    # If Selenium fails, try with requests
    print("Selenium scraping failed, trying with requests...")
    result = scrape_data_with_requests(username, password)
    if result is not None:
        print("Successfully scraped data with requests")
        return result

    print("All scraping methods failed")
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_attendance', methods=['POST', 'GET'])
@limiter.limit("100 per day")
def attendance():
    # Log the request method for debugging
    print(f"Request method: {request.method}")
    print(f"Request headers: {request.headers}")

    if request.method == 'GET':
        return jsonify({'message': 'Please use POST method with username and password'}), 200

    # Handle POST request
    try:
        data = request.get_json()
        print(f"Request data type: {type(data)}")

        if not data:
            # Try to get form data if JSON parsing fails
            username = request.form.get('username')
            password = request.form.get('password')
            print("Falling back to form data")
        else:
            username = data.get('username')
            password = data.get('password')

        print(f"Username provided: {bool(username)}, Password provided: {bool(password)}")

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400

        result = get_attendance_data(username, password)
        if result is not None:
            return jsonify(result)
        else:
            return jsonify({'error': 'Failed to fetch attendance data. Please try again later.'}), 500
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
