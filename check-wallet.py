#!/usr/bin/env python3
"""
Quick script to check if a wallet is in the keystore
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.wallet_manager import EncryptedKeyStore, WalletOrchestrator, WalletRole

WALLET_ADDRESS = "7QfJQNFJWj98p1hxqdKQFAU6AE5V9K6HVtNNQzEaZ5Ed"

def main():
    passphrase = os.getenv("MM_KEYSTORE_PASSPHRASE", "change-this-in-production")
    keystore = EncryptedKeyStore(passphrase)
    orchestrator = WalletOrchestrator(keystore)
    
    # Restore wallets from keystore
    for address in keystore.list_addresses():
        if not orchestrator.get_wallet_info(address):
            orchestrator.register_wallet(address, role=WalletRole.TRADING, label="keystore")
    
    print(f"Checking for wallet: {WALLET_ADDRESS}")
    print(f"Total wallets in keystore: {len(keystore.list_addresses())}")
    print()
    
    # Check if wallet exists
    all_addresses = keystore.list_addresses()
    if WALLET_ADDRESS in all_addresses:
        print(f"[OK] Wallet found in keystore!")
        wallet_info = orchestrator.get_wallet_info(WALLET_ADDRESS)
        if wallet_info:
            print(f"   Label: {wallet_info.get('label', 'N/A')}")
            print(f"   Role: {wallet_info.get('role', 'N/A')}")
            print(f"   Health: {wallet_info.get('health', 'N/A')}")
    else:
        print(f"[NOT FOUND] Wallet NOT found in keystore")
        print(f"\nAvailable wallets:")
        for addr in all_addresses:
            print(f"   {addr}")
        print(f"\nTo import this wallet, use the 'Import Wallet' feature in the UI")
        print(f"or use the API endpoint: POST /api/wallet/import")

if __name__ == "__main__":
    main()
