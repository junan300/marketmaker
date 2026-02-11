#!/usr/bin/env python3
"""Verify wallet can be accessed with current .env passphrase"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from backend.wallet_manager import EncryptedKeyStore, WalletOrchestrator, WalletRole

def main():
    print("=" * 70)
    print("Wallet Access Verification")
    print("=" * 70)
    print()
    
    # Get passphrase from .env (same way server does)
    passphrase = os.getenv("MM_KEYSTORE_PASSPHRASE", "change-this-in-production")
    print(f"Passphrase from .env: {passphrase[:15]}...")
    print()
    
    # Initialize keystore (same way server does)
    keystore = EncryptedKeyStore(passphrase)
    orchestrator = WalletOrchestrator(keystore)
    
    # List wallets
    addresses = keystore.list_addresses()
    print(f"Wallets in keystore: {len(addresses)}")
    print()
    
    if not addresses:
        print("[WARNING] No wallets found in keystore!")
        return
    
    # Test each wallet
    for addr in addresses:
        print(f"Testing wallet: {addr}")
        
        # Try to get key
        try:
            key = keystore.get_key(addr)
            if key:
                print(f"  [OK] Can decrypt private key")
            else:
                print(f"  [FAIL] Cannot decrypt private key")
                continue
        except Exception as e:
            print(f"  [ERROR] Failed to decrypt: {e}")
            continue
        
        # Try to get wallet info from orchestrator
        try:
            info = orchestrator.get_wallet_info(addr)
            if info:
                print(f"  [OK] Wallet registered in orchestrator")
                print(f"       Label: {info.label}")
                print(f"       Role: {info.role.value}")
            else:
                print(f"  [WARNING] Wallet not registered in orchestrator")
                # Register it
                orchestrator.register_wallet(addr, role=WalletRole.TRADING, label="verified")
                print(f"  [OK] Wallet registered")
        except Exception as e:
            print(f"  [ERROR] Failed to get wallet info: {e}")
    
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    pool_status = orchestrator.get_pool_status()
    print(f"Total wallets in pool: {pool_status.get('total_wallets', 0)}")
    print()
    
    if pool_status['total_wallets'] > 0:
        print("[OK] Wallets are accessible and ready to use!")
        print("     The server should be able to access them.")
    else:
        print("[WARNING] No wallets in pool. Server won't be able to trade.")

if __name__ == "__main__":
    main()
