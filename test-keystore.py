#!/usr/bin/env python3
"""Test keystore with different passphrases"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.wallet_manager import EncryptedKeyStore

def test_passphrase(passphrase, label):
    print(f"\n{'='*70}")
    print(f"Testing with {label}: {passphrase[:15]}...")
    print('='*70)
    try:
        keystore = EncryptedKeyStore(passphrase)
        addresses = keystore.list_addresses()
        print(f"Wallets found: {len(addresses)}")
        
        for addr in addresses:
            print(f"  - {addr}")
            # Try to decrypt
            try:
                key = keystore.get_key(addr)
                if key:
                    print(f"    [OK] Can decrypt wallet")
                else:
                    print(f"    [FAIL] Cannot decrypt wallet")
            except Exception as e:
                print(f"    [ERROR] {e}")
        return addresses
    except Exception as e:
        print(f"[ERROR] Failed to open keystore: {e}")
        return []

if __name__ == "__main__":
    # Test with old passphrase
    old_addrs = test_passphrase("change-this-in-production", "OLD passphrase")
    
    # Test with new passphrase
    new_addrs = test_passphrase("Jjplopeza106..", "NEW passphrase")
    
    print(f"\n{'='*70}")
    print("Summary")
    print('='*70)
    print(f"Old passphrase wallets: {len(old_addrs)}")
    print(f"New passphrase wallets: {len(new_addrs)}")
    
    if old_addrs and not new_addrs:
        print("\n[WARNING] Old passphrase works but new doesn't!")
        print("The migration may have failed, or the old passphrase was different.")
    elif new_addrs and not old_addrs:
        print("\n[OK] New passphrase works! Migration successful.")
    elif old_addrs == new_addrs:
        print("\n[OK] Both passphrases work - wallets are accessible.")
    else:
        print("\n[WARNING] Different wallets found with different passphrases!")
