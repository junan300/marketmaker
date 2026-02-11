#!/usr/bin/env python3
"""
View the keystore passphrase from .env file
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    passphrase = os.getenv("MM_KEYSTORE_PASSPHRASE", "NOT SET")
    
    print("=" * 60)
    print("Keystore Passphrase")
    print("=" * 60)
    print()
    print(f"MM_KEYSTORE_PASSPHRASE: {passphrase}")
    print()
    print("=" * 60)
    print()
    print("Use this passphrase in the UI to export your wallet keys.")
    print("Go to: Account Panel > Export Private Key")
    print()
else:
    print("ERROR: .env file not found!")
    print(f"Expected at: {env_path}")
