#!/usr/bin/env python3
"""
Migrate wallets from old passphrase to new passphrase

This script:
1. Decrypts all wallets using the OLD passphrase
2. Re-encrypts them using the NEW passphrase
3. Updates the keystore file

SECURITY WARNING:
- This script handles sensitive wallet operations
- Never commit backup files (*.backup) to git
- This script is safe to commit (reads from .env, doesn't hardcode secrets)

Usage:
    python migrate-passphrase.py
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
from solders.keypair import Keypair

def main():
    print("=" * 70)
    print("Wallet Passphrase Migration Tool")
    print("=" * 70)
    print()
    print("This will re-encrypt all wallets with a new passphrase.")
    print()
    
    # Get current passphrase
    old_passphrase = os.getenv("MM_KEYSTORE_PASSPHRASE", "change-this-in-production")
    print(f"Current passphrase (from .env): {old_passphrase}")
    print()
    
    # Get new passphrase
    print("Enter NEW passphrase (or press Enter to use current):")
    new_passphrase = input("> ").strip()
    
    if not new_passphrase:
        print("No new passphrase provided. Exiting.")
        return
    
    if new_passphrase == old_passphrase:
        print("New passphrase is the same as old. No migration needed.")
        return
    
    print()
    print("Confirm new passphrase:")
    confirm = input("> ").strip()
    
    if new_passphrase != confirm:
        print("Passphrases don't match! Exiting.")
        return
    
    print()
    print("=" * 70)
    print("Starting migration...")
    print("=" * 70)
    print()
    
    # Load old keystore
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
        import shutil
        shutil.copy2(keystore_path, backup_path)
        print(f"Backup created: {backup_path}")
        print()
    
    # Create new keystore with new passphrase
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
            import json
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
    print(f"Successfully migrated: {migrated}/{len(addresses)}")
    
    if failed:
        print(f"Failed: {len(failed)}")
        for addr in failed:
            print(f"  - {addr}")
        print()
        print("You may need to manually re-import failed wallets.")
    
    print()
    print("=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print()
    print("1. Update your .env file:")
    print(f'   MM_KEYSTORE_PASSPHRASE={new_passphrase}')
    print()
    print("2. Restart the backend server")
    print()
    print("3. Verify wallets are accessible")
    print()
    print("4. Once verified, you can delete the backup:")
    print(f"   {backup_path}")
    print()
    
    # Ask if user wants to update .env automatically
    update_env = input("Update .env file automatically? (y/n): ").lower().strip()
    if update_env == 'y':
        update_env_file(new_passphrase)
        print("✅ .env file updated!")
        print()
        print("Now restart your backend server for changes to take effect.")
    else:
        print("Remember to manually update .env file with the new passphrase!")

def update_env_file(new_passphrase):
    """Update MM_KEYSTORE_PASSPHRASE in .env file"""
    env_path = Path(".env")
    if not env_path.exists():
        print("ERROR: .env file not found!")
        return
    
    # Read current .env
    lines = []
    updated = False
    with open(env_path, 'r') as f:
        for line in f:
            if line.startswith('MM_KEYSTORE_PASSPHRASE='):
                lines.append(f'MM_KEYSTORE_PASSPHRASE={new_passphrase}\n')
                updated = True
            else:
                lines.append(line)
    
    # If not found, append it
    if not updated:
        lines.append(f'\nMM_KEYSTORE_PASSPHRASE={new_passphrase}\n')
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
