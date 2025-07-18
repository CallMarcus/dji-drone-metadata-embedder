# FAQ

## My antivirus blocked the EXE
Some security tools may flag downloaded executables. Verify the download source and allow the file if you trust it, or contact your administrator.

## Winget cannot find package
Winget uses online sources that may be disabled on corporate machines. Ensure your PC has access to the Microsoft Store. If winget still reports "No package found," the package may still be pending publication. Use the manual PowerShell installer instead.

## Bootstrap script fails to determine version
Some networks block access to GitHub or PyPI. The PowerShell bootstrap script now falls back to version `1.0.2` automatically. Use `-Version` to supply a different release if needed.
