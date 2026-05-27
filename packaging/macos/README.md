# macOS Packaging

## Prerequisites

- Xcode Command Line Tools (`xcode-select --install`)
- An Apple Developer account with **Developer ID Application** certificate
- `create-dmg` (`brew install create-dmg`)
- Notarytool credentials stored in your keychain:
  ```bash
  xcrun notarytool store-credentials "tikitaka-dwh" \
      --apple-id your@email.com \
      --team-id XXXXXXXXXX \
      --password <app-specific-password>
  ```

## Build steps

### 1. Create the PyInstaller one-folder bundle

```bash
uv run pyinstaller packaging/pyinstaller.spec
```

Output: `dist/TikiTakaPAYDWH/`

### 2. Wrap in a `.app` bundle

```bash
mkdir -p dist/TikiTakaPAYDWH.app/Contents/{MacOS,Resources,Frameworks}

# Copy PyInstaller output as the executable tree
cp -r dist/TikiTakaPAYDWH/ dist/TikiTakaPAYDWH.app/Contents/MacOS/

# Info.plist
cp packaging/macos/Info.plist dist/TikiTakaPAYDWH.app/Contents/

# App icon (create AppIcon.icns from your PNG with iconutil)
# cp packaging/macos/AppIcon.icns dist/TikiTakaPAYDWH.app/Contents/Resources/
```

### 3. Code-sign (deep, hardened runtime)

```bash
codesign --deep --force --options runtime \
    --entitlements packaging/macos/entitlements.plist \
    --sign "Developer ID Application: Your Name (XXXXXXXXXX)" \
    dist/TikiTakaPAYDWH.app
```

### 4. Create a DMG

```bash
create-dmg \
    --volname "Tiki-Taka PAY DWH" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "TikiTakaPAYDWH.app" 175 190 \
    --hide-extension "TikiTakaPAYDWH.app" \
    --app-drop-link 425 190 \
    "TikiTakaPAYDWH-0.1.0-macOS.dmg" \
    "dist/TikiTakaPAYDWH.app"
```

### 5. Notarise

```bash
xcrun notarytool submit TikiTakaPAYDWH-0.1.0-macOS.dmg \
    --keychain-profile "tikitaka-dwh" \
    --wait

xcrun stapler staple TikiTakaPAYDWH-0.1.0-macOS.dmg
```

### 6. Verify

```bash
spctl --assess --type open --context context:primary-signature \
    -v dist/TikiTakaPAYDWH.app
```

A clean install on macOS should launch without any "unidentified developer" warning.

## Entitlements

Create `packaging/macos/entitlements.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
</dict>
</plist>
```

## Notes

- The `com.apple.security.cs.allow-unsigned-executable-memory` entitlement is required by Python's JIT machinery inside PyInstaller bundles on Apple Silicon.
- Test on both Intel and Apple Silicon (arm64) before releasing; build separate binaries or use `lipo` to create a universal binary if needed.
- Increment `CFBundleVersion` in `Info.plist` for every release.
