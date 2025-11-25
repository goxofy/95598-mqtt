import logging
import os
import re
import time
import random
import base64
import sqlite3
from datetime import datetime
import platform
import numpy as np
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from mqtt_publisher import MQTTPublisher
from utils import ScreenshotOnFailure
from settings import *
from captcha_solver import CaptchaResolver

def base64_to_image(base64_str: str):
    base64_data = re.sub('^data:image/.+;base64,', '', base64_str)
    byte_data = base64.b64decode(base64_data)
    image_data = BytesIO(byte_data)
    img = Image.open(image_data)
    return img

class SGCCSpider:

    def __init__(self, username: str, password: str):
        if 'PYTHON_IN_DOCKER' not in os.environ: 
            import dotenv
            dotenv.load_dotenv(verbose=True)
        self.username = username
        self.password = password
        self.resolver = CaptchaResolver(os.path.join(os.path.dirname(__file__), "captcha.onnx"))

        self.enable_db = os.getenv("ENABLE_DATABASE_STORAGE", "false").lower() == "true"
        self.wait_time = int(os.getenv("DRIVER_IMPLICITY_WAIT_TIME", 60))
        self.max_retries = int(os.getenv("RETRY_TIMES_LIMIT", 5))
        self.login_timeout = int(os.getenv("LOGIN_EXPECTED_TIME", 10))
        self.retry_delay = int(os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT", 10))
        self.ignored_users = os.getenv("IGNORE_USER_ID", "xxxxx,xxxxx").split(",")

    def _click_element(self, driver, by, value):
        element = driver.find_element(by, value)
        WebDriverWait(driver, self.wait_time).until(EC.element_to_be_clickable(element))
        try:
            element.click()
        except Exception:
            driver.execute_script("arguments[0].click();", element)

    def simulate_slide(self, driver, distance):
        slider = driver.find_element(By.CLASS_NAME, "slide-verify-slider-mask-item")
        ActionChains(driver).click_and_hold(slider).perform()
        
        # Simplified Human-like trajectory
        tracks = []
        current = 0
        mid = distance * 3 / 4
        t = 0.2
        v = 0
        
        while current < distance:
            if current < mid:
                a = 2
            else:
                a = -3
            v0 = v
            v = v0 + a * t
            move = v0 * t + 1 / 2 * a * t * t
            current += move
            tracks.append(round(move))
            
        # Fix overshoot/undershoot
        if sum(tracks) < distance:
            tracks.append(distance - sum(tracks))
        elif sum(tracks) > distance:
            tracks[-1] -= (sum(tracks) - distance)

        for x in tracks:
            ActionChains(driver).move_by_offset(xoffset=x, yoffset=0).perform()
            
        time.sleep(0.5)
        ActionChains(driver).release().perform()

    def init_db(self, user_id):
        try:
            db_name = os.getenv("DB_NAME", "homeassistant.db")
            if 'PYTHON_IN_DOCKER' in os.environ: 
                db_name = "/data/" + db_name
            else:
                db_name = "./" + db_name
            self.conn = sqlite3.connect(db_name)
            self.conn.cursor()
            
            self.table_daily = f"daily{user_id}"
            self.conn.execute(f'''CREATE TABLE IF NOT EXISTS {self.table_daily} (
                    date DATE PRIMARY KEY NOT NULL, 
                    usage REAL NOT NULL)''')
            
            self.table_meta = f"data{user_id}"
            self.conn.execute(f'''CREATE TABLE IF NOT EXISTS {self.table_meta} (
                    name TEXT PRIMARY KEY NOT NULL,
                    value TEXT NOT NULL)''')
            return True
        except sqlite3.Error as e:
            logging.debug(f"DB Error: {e}")
            return False

    def db_insert_usage(self, data: dict):
        if not self.conn: return
        try:
            sql = f"INSERT OR REPLACE INTO {self.table_daily} VALUES(strftime('%Y-%m-%d','{data['date']}'),{data['usage']});"
            self.conn.execute(sql)
            self.conn.commit()
        except Exception as e:
            logging.debug(f"DB Insert Error: {e}")

    def db_insert_meta(self, data: dict):
        if not self.conn: return
        try:
            sql = f"INSERT OR REPLACE INTO {self.table_meta} VALUES('{data['name']}','{data['value']}');"
            self.conn.execute(sql)
            self.conn.commit()
        except Exception as e:
            logging.debug(f"DB Insert Error: {e}")

    def init_driver(self):
        if platform.system() == 'Windows':
            driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()))
        else:
            from selenium.webdriver.chrome.service import Service as ChromeService
            from webdriver_manager.chrome import ChromeDriverManager
            
            options = webdriver.ChromeOptions()
            options.add_argument('--incognito')
            options.add_argument("--start-maximized")
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument("--window-size=1920,1080")
            
            driver_path = ChromeDriverManager().install()
            driver = webdriver.Chrome(options=options, service=ChromeService(driver_path))
            driver.implicitly_wait(self.wait_time)
        return driver

    @ScreenshotOnFailure.watch
    def perform_login(self, driver):
        try:
            driver.get(URL_LOGIN)
            WebDriverWait(driver, self.wait_time).until(EC.visibility_of_element_located((By.CLASS_NAME, "user")))
        except:
            logging.debug(f"Failed to load login page: {URL_LOGIN}")
        
        time.sleep(self.retry_delay * 2)
        self._click_element(driver, By.CLASS_NAME, "user")
        self._click_element(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
        time.sleep(self.retry_delay)
        self._click_element(driver, By.XPATH, '//*[@id="login_box"]/div[2]/div[1]/form/div[1]/div[3]/div/span[2]')
        time.sleep(self.retry_delay)

        inputs = driver.find_elements(By.CLASS_NAME, "el-input__inner")
        logging.info("Inputting username...")
        inputs[0].send_keys(self.username)
        logging.info("Inputting password...")
        inputs[1].send_keys(self.password)

        self._click_element(driver, By.CLASS_NAME, "el-button.el-button--primary")
        time.sleep(self.retry_delay * 2)

        for attempt in range(1, self.max_retries + 1):
            self._click_element(driver, By.XPATH, '//*[@id="login_box"]/div[1]/div[1]/div[2]/span')
            
            # Get image and dimensions
            js_img = 'return document.getElementById("slideVerify").childNodes[0].toDataURL("image/png");'
            base64_img = driver.execute_script(js_img)
            
            # Get rendered width (CSS width)
            js_width = 'return document.getElementById("slideVerify").childNodes[0].clientWidth;'
            rendered_width = driver.execute_script(js_width)
            
            img_data = base64_img.split(',')[1]
            image = base64_to_image(img_data)
            
            # Calculate scale factor: Rendered Width / Actual Image Width
            scale_factor = rendered_width / image.width
            
            gap_pos = self.resolver.solve_gap(image)
            
            # Apply scaling
            final_distance = int(gap_pos * scale_factor)
            
            # Apply manual offset
            slider_offset = int(os.getenv("SLIDER_OFFSET", 0))
            final_distance += slider_offset
            
            logging.info(f"Captcha: Gap={gap_pos}, Scale={scale_factor:.2f}, Offset={slider_offset}, FinalDist={final_distance}")
            
            self.simulate_slide(driver, final_distance)
            time.sleep(self.retry_delay)
            
            if driver.current_url == URL_LOGIN:
                logging.info(f"Login failed (Attempt {attempt}), retrying captcha...")
                self._click_element(driver, By.CLASS_NAME, "el-button.el-button--primary")
                time.sleep(self.retry_delay * 2)
            else:
                return True
        return False
        
    def run(self):
        driver = self.init_driver()
        ScreenshotOnFailure.set_driver(driver)
        driver.maximize_window()
        time.sleep(self.retry_delay)
        logging.info("Driver initialized.")
        
        publisher = MQTTPublisher()
        
        try:
            if self.perform_login(driver):
                logging.info("Login successful!")
            else:
                logging.error("Login failed!")
                driver.quit()
                return
        except Exception as e:
            logging.error(f"Login exception: {e}")
            driver.quit()
            return

        time.sleep(self.retry_delay)
        user_ids = self.get_user_ids(driver)
        logging.info(f"Found users: {user_ids}")

        for index, user_id in enumerate(user_ids):
            if user_id in self.ignored_users:
                logging.info(f"Skipping ignored user: {user_id}")
                continue

            try:
                driver.get(URL_BALANCE)
                time.sleep(self.retry_delay)
                self.select_user(driver, index)
                time.sleep(self.retry_delay)
                
                data = self.collect_data(driver, user_id, index)
                publisher.publish_user_data(user_id, *data)
                
                time.sleep(self.retry_delay)
            except Exception as e:
                logging.error(f"Failed to process user {user_id}: {e}")
                continue

        driver.quit()

    def get_current_user_id(self, driver):
        return driver.find_element(By.XPATH, '//*[@id="app"]/div/div/article/div/div/div[2]/div/div/div[1]/div[2]/div/div/div/div[2]/div/div[1]/div/ul/div/li[1]/span[2]').text
    
    def select_user(self, driver, index):
        elements = driver.find_elements(By.CLASS_NAME, "button_confirm")
        if elements:
            self._click_element(driver, By.XPATH, f'''//*[@id="app"]/div/div[2]/div/div/div/div[2]/div[2]/div/button''')
        time.sleep(self.retry_delay)
        self._click_element(driver, By.CLASS_NAME, "el-input__suffix")
        time.sleep(self.retry_delay)
        self._click_element(driver, By.XPATH, f"/html/body/div[2]/div[1]/div[1]/ul/li[{index+1}]/span")

    def collect_data(self, driver, user_id, index):
        balance = self.get_balance(driver)
        logging.info(f"User {user_id} Balance: {balance}")
        
        time.sleep(self.retry_delay)
        driver.get(URL_USAGE)
        time.sleep(self.retry_delay)
        self.select_user(driver, index)
        time.sleep(self.retry_delay)
        
        yearly_usage, yearly_charge = self.get_yearly_usage(driver)
        logging.info(f"User {user_id} Yearly: {yearly_usage} kWh, {yearly_charge} CNY")

        months, month_usages, month_charges = self.get_monthly_usage(driver)
        
        last_daily_date, last_daily_usage = self.get_daily_usage(driver)
        logging.info(f"User {user_id} Daily: {last_daily_date} - {last_daily_usage} kWh")

        if self.enable_db:
            dates, usages = self.get_recent_daily_usage(driver)
            self.save_to_db(user_id, balance, last_daily_date, last_daily_usage, dates, usages, months, month_usages, month_charges, yearly_charge, yearly_usage)

        current_month_charge = month_charges[-1] if month_charges else None
        current_month_usage = month_usages[-1] if month_usages else None

        return balance, last_daily_date, last_daily_usage, yearly_charge, yearly_usage, current_month_charge, current_month_usage

    def get_user_ids(self, driver):
        try:
            driver.refresh()
            time.sleep(self.retry_delay * 2)
            WebDriverWait(driver, self.wait_time).until(EC.presence_of_element_located((By.CLASS_NAME, 'el-dropdown')))
            self._click_element(driver, By.XPATH, "//div[@class='el-dropdown']/span")
            time.sleep(self.retry_delay)
            
            target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")
            WebDriverWait(driver, self.wait_time).until(EC.visibility_of(target))
            time.sleep(self.retry_delay)
            
            elements = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_elements(By.TAG_NAME, "li")
            return [re.findall("[0-9]+", e.text)[-1] for e in elements]
        except Exception as e:
            logging.error(f"Failed to get user IDs: {e}")
            driver.quit()
            return []

    def get_balance(self, driver):
        try:
            balance = driver.find_element(By.CLASS_NAME, "num").text
            text = driver.find_element(By.CLASS_NAME, "amttxt").text
            return -float(balance) if "欠费" in text else float(balance)
        except:
            return None

    def get_yearly_usage(self, driver):
        try:
            if datetime.now().month == 1:
                self._click_element(driver, By.XPATH, '//*[@id="pane-first"]/div[1]/div/div[1]/div/div/input')
                time.sleep(self.retry_delay)
                driver.find_element(By.XPATH, f"//span[contains(text(), '{datetime.now().year - 1}')]").click()
                time.sleep(self.retry_delay)
            
            self._click_element(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-first']")
            time.sleep(self.retry_delay)
            
            WebDriverWait(driver, self.wait_time).until(EC.visibility_of(driver.find_element(By.CLASS_NAME, "total")))
            
            usage = driver.find_element(By.XPATH, "//ul[@class='total']/li[1]/span").text
            charge = driver.find_element(By.XPATH, "//ul[@class='total']/li[2]/span").text
            return usage, charge
        except Exception as e:
            logging.error(f"Failed to get yearly data: {e}")
            return None, None

    def get_daily_usage(self, driver):
        try:
            self._click_element(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-second']")
            time.sleep(self.retry_delay)
            
            usage_elem = driver.find_element(By.XPATH, "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[2]/div")
            WebDriverWait(driver, self.wait_time).until(EC.visibility_of(usage_elem))
            
            date_elem = driver.find_element(By.XPATH, "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[1]/div")
            return date_elem.text, float(usage_elem.text)
        except Exception as e:
            logging.error(f"Failed to get daily usage: {e}")
            return None, None

    def get_monthly_usage(self, driver):
        try:
            self._click_element(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-first']")
            time.sleep(self.retry_delay)
            
            if datetime.now().month == 1:
                self._click_element(driver, By.XPATH, '//*[@id="pane-first"]/div[1]/div/div[1]/div/div/input')
                time.sleep(self.retry_delay)
                driver.find_element(By.XPATH, f"//span[contains(text(), '{datetime.now().year - 1}')]").click()
                time.sleep(self.retry_delay)

            WebDriverWait(driver, self.wait_time).until(EC.visibility_of(driver.find_element(By.CLASS_NAME, "total")))
            
            text = driver.find_element(By.XPATH, "//*[@id='pane-first']/div[1]/div[2]/div[2]/div/div[3]/table/tbody").text
            items = text.split("\n")
            if "MAX" in items: items.remove("MAX")
            
            data = np.array(items).reshape(-1, 3)
            return [row[0] for row in data], [row[1] for row in data], [row[2] for row in data]
        except Exception as e:
            logging.error(f"Failed to get monthly data: {e}")
            return None, None, None

    def get_recent_daily_usage(self, driver):
        retention = int(os.getenv("DATA_RETENTION_DAYS", 7))
        self._click_element(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-second']")
        time.sleep(self.retry_delay)

        if retention == 7:
            self._click_element(driver, By.XPATH, "//*[@id='pane-second']/div[1]/div/label[1]/span[1]")
        elif retention == 30:
            self._click_element(driver, By.XPATH, "//*[@id='pane-second']/div[1]/div/label[2]/span[1]")
        
        time.sleep(self.retry_delay)
        
        WebDriverWait(driver, self.wait_time).until(EC.visibility_of(driver.find_element(By.XPATH, "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[2]/div")))
        
        rows = driver.find_elements(By.XPATH, "//*[@id='pane-second']/div[2]/div[2]/div[1]/div[3]/table/tbody/tr")
        dates = []
        usages = []
        
        for row in rows:
            date = row.find_element(By.XPATH, "td[1]/div").text
            usage = row.find_element(By.XPATH, "td[2]/div").text
            if usage:
                dates.append(date)
                usages.append(usage)
        return dates, usages

    def save_to_db(self, user_id, balance, last_daily_date, last_daily_usage, dates, usages, months, month_usages, month_charges, yearly_charge, yearly_usage):
        if self.init_db(user_id):
            self.db_insert_meta({'name': 'user', 'value': str(user_id)})
            self.db_insert_meta({'name': 'balance', 'value': str(balance)})
            self.db_insert_meta({'name': 'daily_date', 'value': str(last_daily_date)})
            self.db_insert_meta({'name': 'daily_usage', 'value': str(last_daily_usage)})
            self.db_insert_meta({'name': 'yearly_usage', 'value': str(yearly_usage)})
            self.db_insert_meta({'name': 'yearly_charge', 'value': str(yearly_charge)})
            
            for i in range(len(dates)):
                self.db_insert_usage({'date': dates[i], 'usage': float(usages[i])})
                
            for i in range(len(months)):
                self.db_insert_meta({'name': f"{months[i]}usage", 'value': str(month_usages[i])})
                self.db_insert_meta({'name': f"{months[i]}charge", 'value': str(month_charges[i])})
                
            if month_usages:
                self.db_insert_meta({'name': 'month_usage', 'value': str(month_usages[-1])})
            if month_charges:
                self.db_insert_meta({'name': 'month_charge', 'value': str(month_charges[-1])})
            
            self.conn.close()


