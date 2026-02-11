#!/usr/bin/env python3
"""
Quick script to import a wallet into the encrypted keystore.
Usage: python import-wallet.py <private_key>
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.wallet_manager import EncryptedKeyStore, WalletOrchestrator, WalletRole

def main():
    if len(sys.argv) < 2:
        print("Usage: python import-wallet.py <private_key>")
        print("\nPrivate key formats supported:")
        print("  - Base58: 5KQwr...")
        print("  - Hex: 0x1234... or 1234...")
        print("  - Array: [1,2,3,...]")
        sys.exit(1)
    
    private_key = sys.argv[1]
    
    # Get passphrase from .env
    passphrase = os.getenv("MM_KEYSTORE_PASSPHRASE", "change-this-in-production")
    if passphrase == "change-this-in-production":
        print("⚠️  WARNING: Using default passphrase!")
        print("   Make sure MM_KEYSTORE_PASSPHRASE is set in .env")
    
    # Initialize keystore and orchestrator
    keystore = EncryptedKeyStore(passphrase)
    orchestrator = WalletOrchestrator(keystore)
    
    try:
        import base58
        from solders.keypair import Keypair
        
        # Handle different input formats
        key_bytes = None
        if isinstance(private_key, str):
            # Try base58 decode first
            try:
                key_bytes = base58.b58decode(private_key)
            except:
                # Try hex
                try:
                    key_bytes = bytes.fromhex(private_key.replace("0x", ""))
                except:
                    # Try as array string
                    try:
                        import json
                        key_array = json.loads(private_key)
                        key_bytes = bytes(key_array)
                    except:
                        raise ValueError("Invalid private key format")
        else:
            raise ValueError("Private key must be a string")
        
        # Create keypair and get address
        if len(key_bytes) == 64:
            keypair = Keypair.from_bytes(key_bytes)
        elif len(key_bytes) == 32:
            keypair = Keypair.from_seed(key_bytes)
        else:
            raise ValueError(f"Invalid key length: {len(key_bytes)}. Expected 32 or 64 bytes.")
        
        address = str(keypair.pubkey())
        
        # Check if already exists
        existing = keystore.list_addresses()
        if address in existing:
            print(f"⚠️  Wallet already exists: {address}")
            response = input("Re-import anyway? (y/n): ")
            if response.lower() != "y":
                print("Cancelled.")
                sys.exit(0)
        
        # Store encrypted and register
        keystore.store_key(address, bytes(keypair), label="imported_via_script")
        orchestrator.register_wallet(address, role=WalletRole.TRADING, label="imported via script")
        
        print(f"✅ Wallet imported successfully!")
        print(f"   Address: {address}")
        print(f"   Label: imported via script")
        print(f"   Role: TRADING")
        print(f"\n💡 Wallet is now encrypted and stored in: data/wallets/keystore.enc")
        print(f"   You can use this wallet in the market maker now.")
        
    except Exception as e:
        print(f"❌ Failed to import wallet: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
