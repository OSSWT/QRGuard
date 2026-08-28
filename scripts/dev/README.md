# Run QRGuard from VS Code or PowerShell

Open the repository root in VS Code:

```text
<repository-root>
```

## Fastest VS Code method

1. Open **Run and Debug** with `Ctrl+Shift+D`.
2. Select **Full stack: backend + Android Emulator (live webcam)**.
3. Press `F5` — not the Run button while a Markdown/Python/Dart file is focused.
4. VS Code starts/checks `Small_Phone`, launches the backend with
   `.venv\Scripts\python.exe`, and runs the Flutter app.
5. Use `Shift+F5` to stop the compound debug session.

`Ctrl+Shift+D` only opens the Run and Debug panel. If a `.md` file is selected and
you click the editor Run button, VS Code asks for a Markdown debugger; cancel it
and select the Full Stack profile instead.

## One PowerShell command

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev\Start-QRGuardDevelopment.ps1
```

This checks the environment, boots `Small_Phone`, opens the backend in a separate
PowerShell window, and starts `flutter run` in the current window.

## Individual scripts

```powershell
# Verify paths
.\scripts\dev\Check-QRGuardEnvironment.ps1

# Backend only, using the repository's exact virtual environment
.\scripts\dev\Start-QRGuardBackend.ps1

# Emulator only
.\scripts\dev\Start-QRGuardEmulator.ps1

# Flutter app only (also starts/checks the emulator)
.\scripts\dev\Run-QRGuardApp.ps1
```

The backend interpreter is always resolved as:

```text
<repository-root>\.venv\Scripts\python.exe
```

## Does every run add another icon?

No. `flutter run` installs/replaces the debug build for the same Android
application ID, `com.osswt.qrguard`, so repeated builds keep one icon and retain
that package's local app data. The second icon came from the retired application
ID `my.qrguard.qrguard`, which Android treats as a different app.

The cleanup script removes only that retired package:

```powershell
.\scripts\dev\Remove-OldQRGuardFromEmulator.ps1
```

It does not run `pm clear`, does not uninstall `com.osswt.qrguard`, and does not
touch the deployed backend or cloud data.

## VS Code Tasks alternative

Press `Ctrl+Shift+P`, choose **Tasks: Run Task**, then select any task beginning
with `QRGuard:`. This is useful when you want only the backend, emulator, app, or
old-package cleanup.
