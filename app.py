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
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    # Check if we're running on Render (environment variable check)
    is_render = os.environ.get('RENDER') == 'true'

    if is_render:
        print("Running on Render, using installed ChromeDriver")
        # On Render, use the ChromeDriver installed by build.sh
        chrome_path = "/usr/bin/google-chrome-stable"
        chromedriver_path = "/usr/local/bin/chromedriver"

        options.binary_location = chrome_path
        service = Service(executable_path=chromedriver_path)

        try:
            driver = webdriver.Chrome(service=service, options=options)
            print("Successfully created Chrome driver with explicit paths")
            return driver
        except Exception as e:
            print(f"Error creating Chrome driver with explicit paths: {str(e)}")
            # Fall through to other methods

    # Try different methods to create the driver
    try:
        # First try with ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("Successfully created Chrome driver with ChromeDriverManager")
    except Exception as e:
        print(f"Error using ChromeDriverManager: {str(e)}")
        try:
            # Fallback to direct Chrome instantiation
            driver = webdriver.Chrome(options=options)
            print("Successfully created Chrome driver directly")
        except Exception as e2:
            print(f"Error creating Chrome driver directly: {str(e2)}")
            # Last resort - try with a specific Chrome path
            options.binary_location = "/usr/bin/google-chrome-stable"  # Common location on Linux servers
            driver = webdriver.Chrome(options=options)
            print("Successfully created Chrome driver with binary location")

    return driver

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
