#!/usr/bin/env python3
"""
Simple script to export wallet keys directly

SECURITY WARNING:
- This script handles private keys
- Never commit exported wallet files to git
- Keep exported keys secure and delete after backup
- This script is safe to commit (reads from .env, doesn't hardcode secrets)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import base58

# Load .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.wallet_manager import EncryptedKeyStore, WalletOrchestrator
from solders.keypair import Keypair

WALLET_ADDRESS = "7QfJQNFJWj98p1hxqdKQFAU6AE5V9K6HVtNNQzEaZ5Ed"

def main():
    passphrase = os.getenv("MM_KEYSTORE_PASSPHRASE", "change-this-in-production")
    keystore = EncryptedKeyStore(passphrase)
    
    print("=" * 70)
    print("Wallet Export Tool")
    print("=" * 70)
    print()
    print(f"Wallet Address: {WALLET_ADDRESS}")
    print()
    
    # Get the key
    key_bytes = keystore.get_key(WALLET_ADDRESS)
    if not key_bytes:
        print(f"ERROR: Wallet {WALLET_ADDRESS} not found in keystore!")
        print()
        print("Available wallets:")
        for addr in keystore.list_addresses():
            print(f"  - {addr}")
        return
    
    # Convert to keypair
    keypair = Keypair.from_bytes(key_bytes)
    
    # Export in different formats
    private_key_base58 = base58.b58encode(bytes(keypair)).decode()
    private_key_hex = bytes(keypair).hex()
    private_key_array = list(bytes(keypair))
    
    print("=" * 70)
    print("PRIVATE KEY - KEEP THIS SECURE!")
    print("=" * 70)
    print()
    print("Base58 Format (most common):")
    print("-" * 70)
    print(private_key_base58)
    print()
    print("Hex Format:")
    print("-" * 70)
    print(private_key_hex)
    print()
    print("Array Format (for JSON):")
    print("-" * 70)
    print(str(private_key_array))
    print()
    print("=" * 70)
    print()
    print("WARNING: Keep this private key secure!")
    print("Never share it with anyone or commit it to version control.")
    print()
    
    # Option to save to file
    save = input("Save to file? (y/n): ").lower().strip()
    if save == 'y':
        filename = f"wallet-export-{WALLET_ADDRESS[:8]}.txt"
        with open(filename, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("WALLET EXPORT - KEEP SECURE!\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Wallet Address: {WALLET_ADDRESS}\n\n")
            f.write("Private Key (Base58):\n")
            f.write(private_key_base58 + "\n\n")
            f.write("Private Key (Hex):\n")
            f.write(private_key_hex + "\n\n")
            f.write("Private Key (Array):\n")
            f.write(str(private_key_array) + "\n\n")
            f.write("=" * 70 + "\n")
            f.write("WARNING: Keep this file secure! Delete after use.\n")
            f.write("=" * 70 + "\n")
        print(f"Saved to: {filename}")
        print("Remember to delete this file after backing up your key!")

if __name__ == "__main__":
    main()
