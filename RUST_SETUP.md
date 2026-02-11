# Rust Setup Guide

## After Installing Rust

When you install Rust via rustup, you'll see a message like:
```
Rust is installed now. Great!

To get started you may need to restart your current shell.
This would reload your PATH environment variable to include
Cargo's bin directory (%USERPROFILE%\.cargo\bin).
```

## What to Do Now

### Option 1: Restart Your Terminal (Easiest - Recommended)

1. **Close your current terminal/PowerShell window completely**
2. **Open a NEW terminal/PowerShell window**
3. **Navigate back to your project:**
   ```powershell
   cd C:\Users\jupal\OneDrive\Escritorio\Coding-projects\marketmaker\marketmaker
   ```

### Option 2: Reload PATH in Current Terminal (Windows PowerShell)

If you're using PowerShell, run:
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

### Option 3: Reload PATH in Current Terminal (Windows CMD)

If you're using CMD, close and reopen it (CMD doesn't easily reload PATH).

## Verify Rust is Installed

After restarting your terminal, verify Rust is working:

```bash
rustc --version
cargo --version
```

You should see version numbers. If you get "command not found", the PATH wasn't updated - try Option 1 (restart terminal).

## Continue with Project Setup

Once Rust is verified, continue with the project setup:

1. **Activate your Python virtual environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Install Python dependencies (this will use Rust to compile some packages):**
   ```bash
   pip install -r requirements.txt
   ```

   Note: The first time installing `solders` and related packages may take a few minutes as they compile Rust code.

3. **Continue with the rest of the setup as normal!**

## Troubleshooting

### "rustc is not recognized"
- Make sure you restarted your terminal
- Try Option 1 (restart terminal) - this is the most reliable method

### "cargo is not recognized"
- Same as above - restart your terminal

### Installation takes a long time
- This is normal! Packages like `solders` need to compile Rust code
- First installation may take 5-10 minutes
- Subsequent installations will be faster

### Still having issues?
- Make sure Rust was installed successfully
- Check that `%USERPROFILE%\.cargo\bin` exists
- Restart your computer if needed (this ensures PATH is fully updated)
