# Centralized logging configuration
import logging
import sys
from datetime import datetime
import os

def setup_logging():
    """Configure logging for the application"""
    
    # Get log level from environment
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Setup file handler for production
    if os.getenv('FLASK_ENV') == 'production':
        file_handler = logging.FileHandler('app.log')
        file_handler.setFormatter(formatter)
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            handlers=[console_handler, file_handler]
        )
    else:
        # Development logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            handlers=[console_handler]
        )
    
    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging()