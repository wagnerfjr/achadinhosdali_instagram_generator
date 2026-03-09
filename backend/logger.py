import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(name: str):
    """Sets up a logger that writes to both console and diag.log"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Create formatters
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console Handler
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File Handler (diag.log)
        log_file = "diag.log"
        file_handler = RotatingFileHandler(log_file, maxBytes=1048576, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger
