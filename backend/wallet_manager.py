"""
Multi-Wallet Orchestration Layer

From the architecture guide:
- Wallet pool management with health monitoring
- Wallet selection strategies (round-robin, weighted, health-based, random)
- Coordinated execution patterns
- Encrypted key storage — NEVER plaintext private keys

Security requirements:
- Private keys encrypted at rest with Fernet (AES-128-CBC)
- Passphrase-derived encryption key via PBKDF2
- Keys never logged, never in error messages
- Hot/cold wallet separation
"""

import os
import json
import time
import random
import logging
import hashlib
import base64
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from threading import Lock
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("wallet_manager")

WALLET_DIR = Path("data/wallets")


class WalletRole(Enum):
    TRADING = "trading"         # Active market making
    ACCUMULATION = "accumulation"  # Buying during markdown
    DISTRIBUTION = "distribution"  # Selling during distribution
    TREASURY = "treasury"       # Cold storage, not for automated trading


class WalletHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"       # Recent failures
    UNHEALTHY = "unhealthy"     # Multiple failures, skip this wallet
    DISABLED = "disabled"       # Manually taken offline


class SelectionStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"       # By balance
    RANDOM = "random"           # Harder to detect patterns
    HEALTH_BASED = "health_based"


@dataclass
class WalletInfo:
    """Public wallet information (no private keys)."""
    address: str
    role: WalletRole = WalletRole.TRADING
    health: WalletHealth = WalletHealth.HEALTHY
    balance_sol: float = 0.0
    current_exposure: float = 0.0
    recent_failures: int = 0
    last_used: float = 0.0
    last_success: float = 0.0
    total_trades: int = 0
    label: str = ""

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "role": self.role.value,
            "health": self.health.value,
            "balance_sol": self.balance_sol,
            "current_exposure": self.current_exposure,
            "recent_failures": self.recent_failures,
            "last_used": self.last_used,
            "total_trades": self.total_trades,
            "label": self.label,
        }


# ── Encrypted Key Storage ───────────────────────────────────────────

class EncryptedKeyStore:
    """
    Fernet-encrypted wallet storage.
    Keys are encrypted at rest using a passphrase-derived key.
    Salt is randomly generated per keystore and stored in a companion file.
    """

    # Legacy fixed salt — used to decrypt keystores created before per-keystore salts
    _LEGACY_SALT = b"solana-mm-keystore-v1"

    def __init__(self, passphrase: str, store_path: Path = None):
        self._store_path = store_path or WALLET_DIR / "keystore.enc"
        self._salt_path = self._store_path.with_suffix(".salt")
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._passphrase = passphrase

        salt = self._load_or_create_salt()
        self._fernet = self._derive_fernet(passphrase, salt)

        # If migrating from legacy fixed salt, re-encrypt with new salt
        self._migrate_legacy_salt_if_needed(passphrase)

    def _load_or_create_salt(self) -> bytes:
        """Load existing salt from file, or generate a new random one."""
        if self._salt_path.exists():
            salt = self._salt_path.read_bytes()
            if len(salt) >= 16:
                return salt
            logger.warning("Salt file corrupted, regenerating")

        # No salt file yet — check if a keystore already exists (legacy)
        if self._store_path.exists():
            # Existing keystore with no salt file → legacy fixed salt.
            # We'll migrate after verifying decryption works.
            logger.info("Legacy keystore detected (no salt file). Will migrate to per-keystore salt.")
            return self._LEGACY_SALT

        # Brand-new keystore — generate random salt
        salt = os.urandom(32)
        self._salt_path.write_bytes(salt)
        logger.info("Generated new random salt for keystore")
        return salt

    def _migrate_legacy_salt_if_needed(self, passphrase: str):
        """
        If the keystore was created with the old fixed salt, re-encrypt
        all keys under a new random salt so every installation is unique.
        """
        if self._salt_path.exists():
            return  # Already using per-keystore salt

        if not self._store_path.exists():
            return  # No keystore to migrate

        store = self._load_store()
        if not store:
            return  # Empty keystore, nothing to migrate

        # Decrypt all keys with the legacy fernet (current self._fernet)
        legacy_fernet = self._fernet
        decrypted_entries = {}
        for address, entry in store.items():
            try:
                plaintext = legacy_fernet.decrypt(entry["encrypted_key"].encode())
                decrypted_entries[address] = (plaintext, entry)
            except Exception:
                logger.error(f"Could not decrypt {address[:8]}... during migration — skipping")
                decrypted_entries[address] = (None, entry)

        # Generate new random salt and derive new fernet
        new_salt = os.urandom(32)
        new_fernet = self._derive_fernet(passphrase, new_salt)

        # Re-encrypt all keys with the new salt
        migrated_store = {}
        for address, (plaintext, entry) in decrypted_entries.items():
            if plaintext is None:
                # Keep the entry as-is (couldn't decrypt — don't lose it)
                migrated_store[address] = entry
                continue
            migrated_store[address] = {
                "encrypted_key": new_fernet.encrypt(plaintext).decode(),
                "label": entry.get("label", ""),
                "created_at": entry.get("created_at", 0),
            }

        # Persist new salt and re-encrypted keystore atomically:
        # write salt first so if we crash mid-save, we can still re-derive
        self._salt_path.write_bytes(new_salt)
        self._save_store(migrated_store)
        self._fernet = new_fernet

        logger.info(f"Migrated {len(decrypted_entries)} wallet(s) from legacy fixed salt to per-keystore random salt")

    @staticmethod
    def _derive_fernet(passphrase: str, salt: bytes) -> Fernet:
        """Derive encryption key from passphrase using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return Fernet(key)

    def store_key(self, address: str, private_key_bytes: bytes, label: str = ""):
        """Encrypt and store a private key."""
        encrypted = self._fernet.encrypt(private_key_bytes)

        # Load existing store
        store = self._load_store()
        store[address] = {
            "encrypted_key": encrypted.decode(),
            "label": label,
            "created_at": time.time(),
        }
        self._save_store(store)
        logger.info(f"Wallet stored: {address[:8]}...{address[-4:]}")

    def get_key(self, address: str) -> Optional[bytes]:
        """Decrypt and return a private key. Returns None if not found."""
        store = self._load_store()
        entry = store.get(address)
        if not entry:
            return None
        try:
            return self._fernet.decrypt(entry["encrypted_key"].encode())
        except Exception as e:
            logger.error(f"Failed to decrypt key for {address[:8]}...: {type(e).__name__}")
            return None

    def list_addresses(self) -> list:
        """List all stored wallet addresses (no keys exposed)."""
        store = self._load_store()
        return list(store.keys())

    def remove_key(self, address: str) -> bool:
        store = self._load_store()
        if address in store:
            del store[address]
            self._save_store(store)
            logger.info(f"Wallet removed: {address[:8]}...")
            return True
        return False

    def _load_store(self) -> dict:
        if not self._store_path.exists():
            return {}
        try:
            with open(self._store_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.error("Failed to load keystore — returning empty")
            return {}

    def _save_store(self, store: dict):
        with open(self._store_path, "w") as f:
            json.dump(store, f)


# ── Wallet Pool & Orchestrator ──────────────────────────────────────

class WalletOrchestrator:
    """
    Manages a pool of 10-20 wallets with selection strategies,
    health monitoring, and coordinated execution support.
    """

    def __init__(self, keystore: EncryptedKeyStore):
        self.keystore = keystore
        self._wallets: dict[str, WalletInfo] = {}  # address -> WalletInfo
        self._round_robin_index = 0
        self._lock = Lock()
        self._active_wallets: set[str] = set()  # Set of active wallet addresses

    def register_wallet(
        self,
        address: str,
        role: WalletRole = WalletRole.TRADING,
        label: str = "",
    ) -> WalletInfo:
        """Register a wallet in the pool."""
        with self._lock:
            info = WalletInfo(address=address, role=role, label=label)
            self._wallets[address] = info
            logger.info(f"Wallet registered: {address[:8]}... role={role.value}")
            return info

    def get_wallet(
        self,
        strategy: SelectionStrategy = SelectionStrategy.HEALTH_BASED,
        role: WalletRole = None,
        min_balance: float = 0.01,
        max_exposure: float = None,
        exclude: list = None,
    ) -> Optional[WalletInfo]:
        """
        Select a wallet from the pool based on strategy and criteria.
        Returns None if no suitable wallet is available.
        """
        with self._lock:
            candidates = self._filter_candidates(role, min_balance, max_exposure, exclude)
            if not candidates:
                logger.warning("No suitable wallets available")
                return None

            if strategy == SelectionStrategy.ROUND_ROBIN:
                return self._select_round_robin(candidates)
            elif strategy == SelectionStrategy.WEIGHTED:
                return self._select_weighted(candidates)
            elif strategy == SelectionStrategy.RANDOM:
                return self._select_random(candidates)
            elif strategy == SelectionStrategy.HEALTH_BASED:
                return self._select_health_based(candidates)

            return candidates[0]

    def _filter_candidates(
        self, role, min_balance, max_exposure, exclude
    ) -> list[WalletInfo]:
        exclude_set = set(exclude or [])
        candidates = []
        for addr, info in self._wallets.items():
            if addr in exclude_set:
                continue
            if info.health in (WalletHealth.UNHEALTHY, WalletHealth.DISABLED):
                continue
            if role and info.role != role:
                continue
            if info.balance_sol < min_balance:
                continue
            if max_exposure and info.current_exposure >= max_exposure:
                continue
            candidates.append(info)
        return candidates

    def _select_round_robin(self, candidates: list) -> WalletInfo:
        self._round_robin_index = self._round_robin_index % len(candidates)
        selected = candidates[self._round_robin_index]
        self._round_robin_index += 1
        return selected

    def _select_weighted(self, candidates: list) -> WalletInfo:
        """Weight by balance — larger wallets get more trades."""
        total_balance = sum(w.balance_sol for w in candidates)
        if total_balance <= 0:
            return random.choice(candidates)
        weights = [w.balance_sol / total_balance for w in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _select_random(self, candidates: list) -> WalletInfo:
        return random.choice(candidates)

    def _select_health_based(self, candidates: list) -> WalletInfo:
        """Prioritize healthy wallets with recent successes."""
        # Sort: healthy first, then by recent_failures (ascending), then last_success (descending)
        candidates.sort(
            key=lambda w: (
                0 if w.health == WalletHealth.HEALTHY else 1,
                w.recent_failures,
                -w.last_success,
            )
        )
        return candidates[0]

    # ── Health Management ───────────────────────────────────────────

    def record_success(self, address: str):
        with self._lock:
            if address in self._wallets:
                w = self._wallets[address]
                w.recent_failures = 0
                w.last_success = time.time()
                w.last_used = time.time()
                w.total_trades += 1
                w.health = WalletHealth.HEALTHY

    def record_failure(self, address: str):
        with self._lock:
            if address in self._wallets:
                w = self._wallets[address]
                w.recent_failures += 1
                w.last_used = time.time()
                if w.recent_failures >= 5:
                    w.health = WalletHealth.UNHEALTHY
                    logger.warning(f"Wallet {address[:8]}... marked UNHEALTHY")
                elif w.recent_failures >= 2:
                    w.health = WalletHealth.DEGRADED

    def update_balance(self, address: str, balance_sol: float):
        with self._lock:
            if address in self._wallets:
                self._wallets[address].balance_sol = balance_sol

    async def refresh_balances(self, rpc_url: str):
        """Fetch current balances from Solana RPC for all wallets."""
        from solana.rpc.async_api import AsyncClient
        from solders.pubkey import Pubkey
        
        async with AsyncClient(rpc_url) as client:
            for address in list(self._wallets.keys()):
                try:
                    pubkey = Pubkey.from_string(address)
                    resp = await client.get_balance(pubkey)
                    if resp.value is not None:
                        balance_sol = resp.value / 1e9  # Convert lamports to SOL
                        self.update_balance(address, balance_sol)
                except Exception as e:
                    logger.warning(f"Failed to fetch balance for {address[:8]}...: {e}")

    def update_exposure(self, address: str, exposure: float):
        with self._lock:
            if address in self._wallets:
                self._wallets[address].current_exposure = exposure

    def disable_wallet(self, address: str):
        with self._lock:
            if address in self._wallets:
                self._wallets[address].health = WalletHealth.DISABLED
                logger.info(f"Wallet {address[:8]}... disabled")

    def enable_wallet(self, address: str):
        with self._lock:
            if address in self._wallets:
                self._wallets[address].health = WalletHealth.HEALTHY
                self._wallets[address].recent_failures = 0
                logger.info(f"Wallet {address[:8]}... re-enabled")

    # ── Pool Status ─────────────────────────────────────────────────

    def get_pool_status(self) -> dict:
        with self._lock:
            wallets = [w.to_dict() for w in self._wallets.values()]
            return {
                "total_wallets": len(self._wallets),
                "healthy": sum(1 for w in self._wallets.values() if w.health == WalletHealth.HEALTHY),
                "degraded": sum(1 for w in self._wallets.values() if w.health == WalletHealth.DEGRADED),
                "unhealthy": sum(1 for w in self._wallets.values() if w.health == WalletHealth.UNHEALTHY),
                "disabled": sum(1 for w in self._wallets.values() if w.health == WalletHealth.DISABLED),
                "total_balance_sol": sum(w.balance_sol for w in self._wallets.values()),
                "total_exposure_sol": sum(w.current_exposure for w in self._wallets.values()),
                "wallets": wallets,
            }

    def get_wallet_info(self, address: str) -> Optional[dict]:
        with self._lock:
            if address in self._wallets:
                return self._wallets[address].to_dict()
            return None

    def get_signing_key(self, address: str) -> Optional[bytes]:
        """
        Get the decrypted private key for transaction signing.
        NEVER log this. NEVER include in error messages.
        """
        return self.keystore.get_key(address)

    # ── Active Wallet Management ──────────────────────────────────────

    def set_active_wallets(self, addresses: list[str]):
        """Set which wallets are active (for display and manual trading)."""
        with self._lock:
            # Only set wallets that exist
            valid_addresses = [addr for addr in addresses if addr in self._wallets]
            self._active_wallets = set(valid_addresses)
            logger.info(f"Active wallets set: {len(valid_addresses)} wallets")

    def add_active_wallet(self, address: str):
        """Add a wallet to the active set."""
        with self._lock:
            if address in self._wallets:
                self._active_wallets.add(address)
                logger.info(f"Wallet {address[:8]}... added to active set")

    def remove_active_wallet(self, address: str):
        """Remove a wallet from the active set."""
        with self._lock:
            self._active_wallets.discard(address)
            logger.info(f"Wallet {address[:8]}... removed from active set")

    def get_active_wallets(self) -> list[str]:
        """Get list of active wallet addresses."""
        with self._lock:
            return list(self._active_wallets)

    def get_primary_wallet(self) -> Optional[WalletInfo]:
        """Get the primary active wallet (first one, or first enabled wallet if none active)."""
        with self._lock:
            if self._active_wallets:
                # Return first active wallet
                for addr in self._active_wallets:
                    if addr in self._wallets:
                        return self._wallets[addr]
            # Fallback to first enabled wallet
            enabled = [w for w in self._wallets.values() 
                      if w.health != WalletHealth.DISABLED]
            if enabled:
                return enabled[0]
            return None
