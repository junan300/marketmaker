# Security Guide - What NOT to Commit to GitHub

## ⚠️ CRITICAL: Never Commit These Files

### 🔴 NEVER COMMIT (High Risk)

1. **`.env` file** - Contains your keystore passphrase and API keys
2. **`data/wallets/keystore.enc`** - Encrypted wallet storage (even encrypted, don't commit)
3. **`wallet.json`** - Plaintext wallet files (if any exist)
4. **`wallet-export-*.txt`** - Exported private keys
5. **`*.backup`** - Backup files that may contain sensitive data
6. **`data/*.db`** - Database files with trading history
7. **`data/*.log`** - Log files that may contain sensitive information

### 🟡 CONSIDER NOT COMMITTING (Medium Risk)

These scripts handle sensitive operations. While they're safe to commit (they don't contain secrets), you may prefer to keep them private:

- `export-wallet-simple.py` - Exports private keys
- `migrate-passphrase.py` - Handles passphrase migration
- `view-passphrase.py` - Shows passphrase from .env
- `check-wallet.py` - Checks wallet status

**Why it's safe:** These scripts read from `.env` (which is gitignored) and don't hardcode any secrets.

**Why you might exclude them:** They reveal how your security system works.

## ✅ Safe to Commit

- Source code (`.py`, `.tsx`, `.ts` files)
- Configuration files (`package.json`, `requirements.txt`)
- Documentation (`.md` files)
- Scripts that don't handle sensitive data

## Current .gitignore Protection

Your `.gitignore` already excludes:
- ✅ `.env` files
- ✅ `data/wallets/` directory
- ✅ `*.enc` files
- ✅ `*.backup` files
- ✅ `wallet-export-*.txt` files
- ✅ Database and log files

## Before Committing to GitHub

### Quick Security Check

```bash
# Check what will be committed
git status

# Check for any sensitive files
git diff --cached

# Verify .env is ignored
git check-ignore .env
# Should output: .env
```

### If You Accidentally Committed Sensitive Data

**If you haven't pushed yet:**
```bash
# Remove from staging
git reset HEAD <file>

# Remove from history (if already committed)
git rm --cached <file>
```

**If you already pushed:**
1. **IMMEDIATELY** change your passphrase: `python migrate-passphrase.py`
2. **IMMEDIATELY** rotate any API keys in `.env`
3. Consider the repository compromised
4. Use GitHub's secret scanning to check if secrets were exposed
5. Consider making the repo private or creating a new one

## Best Practices

1. ✅ **Always check `git status`** before committing
2. ✅ **Use `.gitignore`** - it's already set up correctly
3. ✅ **Never commit `.env`** - even with fake values
4. ✅ **Review diffs** before pushing
5. ✅ **Use private repos** for projects with wallet management
6. ✅ **Rotate secrets** if accidentally exposed

## Script Security

The utility scripts (`export-wallet-simple.py`, etc.) are **safe to commit** because:
- They read secrets from `.env` (which is gitignored)
- They don't hardcode any passwords or keys
- They require the passphrase to be in `.env` to work

However, if you want extra security, you can add them to `.gitignore`:

```gitignore
# Optional: Exclude wallet management scripts
export-wallet-simple.py
migrate-passphrase.py
view-passphrase.py
check-wallet.py
```

## Verification

Run this to verify your setup:

```bash
# Should show .env is ignored
git check-ignore .env data/wallets/keystore.enc

# Should NOT show any sensitive files in git status
git status | grep -E "\.env|keystore|wallet|export"
```

If the second command shows any files, they're NOT properly ignored!
