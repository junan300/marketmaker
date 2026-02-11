#!/usr/bin/env python3
"""
Non-interactive passphrase migration script
Migrates keystore from old passphrase to new passphrase

Usage:
    python migrate-passphrase-auto.py <old_passphrase> <new_passphrase>
    
Or set environment variables:
    OLD_PASSPHRASE=old_pass OLD_PASSPHRASE=new_pass python migrate-passphrase-auto.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.wallet_manager import EncryptedKeyStore
import shutil
import json

def main():
    # Get passphrases from command line or environment
    if len(sys.argv) >= 3:
        old_passphrase = sys.argv[1]
        new_passphrase = sys.argv[2]
    else:
        old_passphrase = os.getenv("OLD_PASSPHRASE")
        new_passphrase = os.getenv("NEW_PASSPHRASE")
        
        if not old_passphrase or not new_passphrase:
            print("Usage: python migrate-passphrase-auto.py <old_passphrase> <new_passphrase>")
            print("   Or: OLD_PASSPHRASE=old NEW_PASSPHRASE=new python migrate-passphrase-auto.py")
            sys.exit(1)
    
    print("=" * 70)
    print("Wallet Passphrase Migration (Auto)")
    print("=" * 70)
    print()
    print(f"Old passphrase: {old_passphrase[:10]}...")
    print(f"New passphrase: {new_passphrase[:10]}...")
    print()
    
    if old_passphrase == new_passphrase:
        print("Passphrases are the same. No migration needed.")
        return
    
    # Load old keystore
    print("Loading old keystore...")
    old_keystore = EncryptedKeyStore(old_passphrase)
    addresses = old_keystore.list_addresses()
    
    if not addresses:
        print("No wallets found in keystore. Nothing to migrate.")
        return
    
    print(f"Found {len(addresses)} wallet(s) to migrate:")
    for addr in addresses:
        print(f"  - {addr}")
    print()
    
    # Backup old keystore
    keystore_path = Path("data/wallets/keystore.enc")
    backup_path = Path("data/wallets/keystore.enc.backup")
    
    if keystore_path.exists():
        shutil.copy2(keystore_path, backup_path)
        print(f"[OK] Backup created: {backup_path}")
        print()
    
    # Create new keystore with new passphrase
    print("Creating new keystore with new passphrase...")
    new_keystore = EncryptedKeyStore(new_passphrase)
    
    # Migrate each wallet
    migrated = 0
    failed = []
    
    for address in addresses:
        try:
            # Get key from old keystore
            key_bytes = old_keystore.get_key(address)
            if not key_bytes:
                print(f"  [SKIP] {address[:8]}... - Could not decrypt with old passphrase")
                failed.append(address)
                continue
            
            # Get label from old keystore
            old_store = old_keystore._load_store()
            label = old_store.get(address, {}).get("label", "")
            
            # Store in new keystore
            new_keystore.store_key(address, key_bytes, label=label)
            print(f"  [OK] {address[:8]}... - Migrated successfully")
            migrated += 1
            
        except Exception as e:
            print(f"  [ERROR] {address[:8]}... - {e}")
            failed.append(address)
    
    print()
    print("=" * 70)
    print("Migration Complete")
    print("=" * 70)
    print()
    print(f"[OK] Successfully migrated: {migrated}/{len(addresses)}")
    
    if failed:
        print(f"[ERROR] Failed: {len(failed)}")
        for addr in failed:
            print(f"  - {addr}")
        print()
        print("You may need to manually re-import failed wallets.")
    
    print()
    print("[OK] Keystore has been re-encrypted with new passphrase!")
    print()
    print("Next: Restart your backend server to use the new passphrase.")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
