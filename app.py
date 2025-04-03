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

    # Find Chrome binary
    chrome_binary = None
    possible_paths = [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/local/bin/google-chrome",
        "/opt/google/chrome/google-chrome"
    ]

    # Check if Chrome exists in any of the possible paths
    for path in possible_paths:
        if os.path.exists(path):
            chrome_binary = path
            print(f"Found Chrome binary at: {chrome_binary}")
            break

    if not chrome_binary:
        print("Chrome binary not found in standard locations. Trying to find it...")
        try:
            # Try to find Chrome using 'which' command
            import subprocess
            result = subprocess.run(['which', 'google-chrome-stable'], capture_output=True, text=True)
            if result.stdout.strip():
                chrome_binary = result.stdout.strip()
                print(f"Found Chrome using 'which' command at: {chrome_binary}")
        except Exception as e:
            print(f"Error finding Chrome with 'which' command: {str(e)}")

    # Set up Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    # If Chrome binary was found, set it explicitly
    if chrome_binary:
        print(f"Setting Chrome binary location to: {chrome_binary}")
        options.binary_location = chrome_binary

    # Find ChromeDriver
    chromedriver_path = None
    possible_driver_paths = [
        "/usr/local/bin/chromedriver",
        "/usr/bin/chromedriver"
    ]

    for path in possible_driver_paths:
        if os.path.exists(path):
            chromedriver_path = path
            print(f"Found ChromeDriver at: {chromedriver_path}")
            break

    # Try different methods to create the driver
    try:
        if chromedriver_path:
            # Use the found ChromeDriver
            print(f"Creating Chrome driver with explicit ChromeDriver path: {chromedriver_path}")
            service = Service(executable_path=chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            print("Successfully created Chrome driver with explicit ChromeDriver path")
        else:
            # Try with ChromeDriverManager
            print("Creating Chrome driver with ChromeDriverManager")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            print("Successfully created Chrome driver with ChromeDriverManager")

        return driver
    except Exception as e:
        print(f"Error creating Chrome driver with primary method: {str(e)}")

        # Fallback methods
        try:
            # Try direct instantiation
            print("Trying direct Chrome instantiation")
            driver = webdriver.Chrome(options=options)
            print("Successfully created Chrome driver directly")
            return driver
        except Exception as e2:
            print(f"Error with direct instantiation: {str(e2)}")

            # Last resort - try with default Service
            try:
                print("Trying with default Service")
                service = Service()
                driver = webdriver.Chrome(service=service, options=options)
                print("Successfully created Chrome driver with default Service")
                return driver
            except Exception as e3:
                print(f"All methods failed. Final error: {str(e3)}")
                raise Exception(f"Failed to create Chrome driver after multiple attempts: {str(e3)}")

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

def get_attendance_data(username, password):
    future = executor.submit(lambda: scrape_data(create_driver(), username, password))
    try:
        return future.result(timeout=60)  # 1 minute timeout
    except concurrent.futures.TimeoutError:
        print("Scraping operation timed out")
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
