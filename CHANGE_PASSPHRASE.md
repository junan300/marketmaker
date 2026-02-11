# How to Change Your Keystore Passphrase

## Important Note

**You CANNOT just change the `.env` file** - existing wallets are encrypted with the OLD passphrase, so they won't be accessible with the new one.

## Solution: Migration Script

I've created a migration script that will:
1. ✅ Decrypt all wallets using the OLD passphrase
2. ✅ Re-encrypt them with the NEW passphrase  
3. ✅ Update your `.env` file automatically
4. ✅ Create a backup of your old keystore

## Steps to Change Passphrase

### Step 1: Run the Migration Script

```bash
python migrate-passphrase.py
```

The script will:
- Show your current passphrase (from `.env`)
- Ask for your NEW passphrase
- Confirm the new passphrase
- Migrate all wallets automatically
- Optionally update your `.env` file

### Step 2: Restart Backend Server

After migration, restart your backend server:
- If using PM2: `pm2 restart marketmaker-backend`
- If running manually: Stop and restart the server

### Step 3: Verify

1. Check that wallets are accessible in the UI
2. Try exporting a wallet key with the NEW passphrase
3. Once verified, you can delete the backup: `data/wallets/keystore.enc.backup`

## Manual Method (Alternative)

If you prefer to do it manually:

1. **Export all wallets** using the old passphrase
2. **Change `.env`** to the new passphrase
3. **Restart server**
4. **Re-import all wallets** (they'll be encrypted with the new passphrase)

## Security Tips

- ✅ Use a strong, unique passphrase
- ✅ Store it securely (password manager)
- ✅ Keep the backup until you verify everything works
- ✅ Never commit the passphrase to version control

## Troubleshooting

**If migration fails:**
- Check that the old passphrase in `.env` is correct
- Verify the keystore file exists: `data/wallets/keystore.enc`
- Check the backup file: `data/wallets/keystore.enc.backup`

**If wallets don't work after migration:**
- Restore from backup: Copy `keystore.enc.backup` to `keystore.enc`
- Revert `.env` to old passphrase
- Restart server
- Try migration again
