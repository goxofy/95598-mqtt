import logging
import os
import sys
import time
import schedule
import random
from datetime import datetime, timedelta
from settings import *
from sgcc_client import SGCCSpider
from utils import ScreenshotOnFailure

def setup_logging(level: str):
    logger = logging.getLogger()
    logger.setLevel(level)
    logging.getLogger("urllib3").setLevel(logging.CRITICAL)
    format = logging.Formatter("%(asctime)s  [%(levelname)-8s] ---- %(message)s", "%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(format)
    logger.addHandler(sh)

def execute_job(spider: SGCCSpider, max_retries: int):
    for attempt in range(1, max_retries + 1):
        try:
            spider.run()
            next_run = schedule.next_run()
            if next_run:
                logging.info(f"Going to sleep. Next run scheduled at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            return
        except Exception as e:
            logging.error(f"Job failed (Attempt {attempt}/{max_retries}): {e}")
            continue

def main():
    if 'PYTHON_IN_DOCKER' not in os.environ: 
        import dotenv
        dotenv.load_dotenv(verbose=True)
        
    phone_number = os.getenv("PHONE_NUMBER")
    password = os.getenv("PASSWORD")
    job_start_time = os.getenv("JOB_START_TIME", "07:00")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    max_retries = int(os.getenv("RETRY_TIMES_LIMIT", 5))
    
    setup_logging(log_level)
    
    if not phone_number or not password:
        logging.error("Missing credentials (PHONE_NUMBER or PASSWORD).")
        sys.exit(1)

    logging.info("Starting SGCC Electricity Spider...")
    
    ScreenshotOnFailure.init(root_dir='./errors')
    
    spider = SGCCSpider(phone_number, password)

    # Random delay logic
    random_delay = random.randint(-10, 10)
    parsed_time = datetime.strptime(job_start_time, "%H:%M") + timedelta(minutes=random_delay)
    next_run_time = parsed_time + timedelta(hours=12)
    
    logging.info(f"Scheduled runs at {parsed_time.strftime('%H:%M')} and {next_run_time.strftime('%H:%M')}")
    
    schedule.every().day.at(parsed_time.strftime("%H:%M")).do(execute_job, spider, max_retries)
    schedule.every().day.at(next_run_time.strftime("%H:%M")).do(execute_job, spider, max_retries)
    
    # Run immediately on startup
    execute_job(spider, max_retries)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
