#!/usr/bin/env python3
"""
Quick setup verification script
Run this to check if your environment is set up correctly
"""

import sys
import subprocess
import os

def check_python_version():
    """Check if Python version is 3.9+"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"[FAIL] Python {version.major}.{version.minor}.{version.micro} (Need 3.9+)")
        return False

def check_node_version():
    """Check if Node.js is installed"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[OK] Node.js {result.stdout.strip()}")
            return True
        else:
            print("[FAIL] Node.js not found")
            return False
    except FileNotFoundError:
        print("[FAIL] Node.js not installed")
        return False

def check_python_dependencies():
    """Check if Python dependencies are installed"""
    try:
        import fastapi
        import solana
        import solders
        print("[OK] Python dependencies installed")
        return True
    except ImportError as e:
        print(f"[FAIL] Missing Python dependency: {e.name}")
        print("  Run: pip install -r requirements.txt")
        return False

def check_node_dependencies():
    """Check if Node.js dependencies are installed"""
    if os.path.exists('node_modules'):
        print("[OK] Node.js dependencies installed")
        return True
    else:
        print("[FAIL] Node.js dependencies not installed")
        print("  Run: npm install")
        return False

def check_env_file():
    """Check if .env file exists"""
    if os.path.exists('.env'):
        print("[OK] .env file exists")
        return True
    else:
        print("[FAIL] .env file not found")
        print("  Create .env file with configuration (see SETUP.md)")
        return False

def check_backend_structure():
    """Check if backend files exist"""
    required_files = [
        'backend/__init__.py',
        'backend/main.py',
        'backend/config.py',
        'backend/solana_client.py',
        'backend/market_maker.py'
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"[OK] {file} exists")
        else:
            print(f"[FAIL] {file} missing")
            all_exist = False
    
    return all_exist

def main():
    print("=" * 50)
    print("Solana Market Maker - Setup Verification")
    print("=" * 50)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Node.js", check_node_version),
        ("Python Dependencies", check_python_dependencies),
        ("Node.js Dependencies", check_node_dependencies),
        ("Environment File", check_env_file),
        ("Backend Structure", check_backend_structure),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"Checking {name}...")
        results.append(check_func())
        print()
    
    print("=" * 50)
    if all(results):
        print("[SUCCESS] All checks passed! You're ready to go.")
        print()
        print("Next steps:")
        print("1. Start backend: python -m uvicorn backend.main:app --reload --port 8000")
        print("2. Start frontend: npm run dev")
        print("3. Open browser: http://localhost:3000")
    else:
        print("[FAIL] Some checks failed. Please fix the issues above.")
    print("=" * 50)

if __name__ == "__main__":
    main()
