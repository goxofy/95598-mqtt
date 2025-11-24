"""
This script provides a wrapper to save screenshots of errors.
"""

import os
import logging
import time
from functools import wraps

class ScreenshotOnFailure:
    _driver = None
    _root_dir = "./errors"

    @classmethod
    def set_driver(cls, driver):
        cls._driver = driver

    @classmethod
    def init(cls, root_dir="./errors"):
        cls._root_dir = root_dir
        if not os.path.exists(cls._root_dir):
            os.makedirs(cls._root_dir)

    @classmethod
    def capture(cls, filename="error.png"):
        if cls._driver:
            try:
                path = os.path.join(cls._root_dir, filename)
                cls._driver.save_screenshot(path)
                logging.info(f"Screenshot saved to {path}")
            except Exception as e:
                logging.error(f"Failed to save screenshot: {e}")

    @classmethod
    def watch(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                cls.capture(f"error_{timestamp}.png")
                raise e
        return wrapper

