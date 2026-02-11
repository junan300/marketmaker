#!/usr/bin/env python3
"""
Health Check Script for Market Maker
Runs every minute to ensure services are up
Can be scheduled with Windows Task Scheduler or cron
"""

import requests
import sys
import time
from pathlib import Path

BACKEND_URL = "http://localhost:8000/health"
FRONTEND_URL = "http://localhost:3000"
MAX_RETRIES = 3
RETRY_DELAY = 5

def check_service(url, name):
    """Check if a service is responding."""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return True, None
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                return False, str(e)
    return False, "Max retries exceeded"

def main():
    """Main health check function."""
    backend_ok, backend_error = check_service(BACKEND_URL, "Backend")
    frontend_ok, frontend_error = check_service(FRONTEND_URL, "Frontend")
    
    log_file = Path("data/health-check.log")
    log_file.parent.mkdir(exist_ok=True)
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    with open(log_file, "a") as f:
        if backend_ok and frontend_ok:
            f.write(f"{timestamp} - OK: Both services healthy\n")
            print(f"{timestamp} - OK: Both services healthy")
            return 0
        else:
            status = []
            if not backend_ok:
                status.append(f"Backend DOWN: {backend_error}")
            if not frontend_ok:
                status.append(f"Frontend DOWN: {frontend_error}")
            
            error_msg = f"{timestamp} - ERROR: {' | '.join(status)}\n"
            f.write(error_msg)
            print(error_msg.strip())
            return 1

if __name__ == "__main__":
    sys.exit(main())
