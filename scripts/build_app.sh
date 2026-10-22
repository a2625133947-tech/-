#!/bin/bash
# ==============================================================================
# AI Hedge Fund - macOS App Bundle Builder
# ==============================================================================
# Installs single official "AI Hedge Fund.app" to /Applications
# ==============================================================================

set -euo pipefail

PROJECT_ROOT="/Users/niuyufei/ai-hedge-fund-2025"
APP_NAME="AI Hedge Fund.app"
TARGET_APP="/Applications/$APP_NAME"
USER_TARGET_APP="$HOME/Applications/$APP_NAME"
DIST_APP="$PROJECT_ROOT/dist/$APP_NAME"
FAVICON="$PROJECT_ROOT/app/frontend/public/favicon.ico"

echo "=== Building $APP_NAME for /Applications ==="

# Clean up duplicate locations
rm -rf "$TARGET_APP"
rm -rf "$USER_TARGET_APP" 2>/dev/null || true
rm -rf "$DIST_APP" 2>/dev/null || true

# 1. Create App Bundle Directory Structure directly in /Applications
CONTENTS_DIR="$TARGET_APP/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# 2. Build AppIcon.icns from favicon.ico
echo "Generating application icon from $FAVICON..."
ICONSET_DIR="/tmp/ai_hedge_fund_icon.iconset"
TEMP_PNG="/tmp/ai_hedge_fund_icon_base.png"
rm -rf "$ICONSET_DIR" "$TEMP_PNG"
mkdir -p "$ICONSET_DIR"

# Extract base PNG from favicon.ico
sips -s format png "$FAVICON" --out "$TEMP_PNG" >/dev/null 2>&1

# Generate standard iconset sizes
sips -z 16 16     "$TEMP_PNG" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null 2>&1
sips -z 32 32     "$TEMP_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null 2>&1
sips -z 32 32     "$TEMP_PNG" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null 2>&1
sips -z 64 64     "$TEMP_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null 2>&1
sips -z 128 128   "$TEMP_PNG" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null 2>&1
sips -z 256 256   "$TEMP_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null 2>&1
sips -z 256 256   "$TEMP_PNG" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null 2>&1
sips -z 512 512   "$TEMP_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null 2>&1
sips -z 512 512   "$TEMP_PNG" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null 2>&1

iconutil -c icns "$ICONSET_DIR" -o "$RESOURCES_DIR/AppIcon.icns"
rm -rf "$ICONSET_DIR" "$TEMP_PNG"

# 3. Create Info.plist
cat << 'EOF' > "$CONTENTS_DIR/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>zh_CN</string>
    <key>CFBundleExecutable</key>
    <string>AI Hedge Fund</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.aihedgefund.macos</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>AI Hedge Fund</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.finance</string>
</dict>
</plist>
EOF

# 4. Create PkgInfo
printf "APPL????" > "$CONTENTS_DIR/PkgInfo"

# 5. Create Executable Wrapper
EXECUTABLE="$MACOS_DIR/AI Hedge Fund"
cat << 'EOF' > "$EXECUTABLE"
#!/bin/bash
PROJECT_ROOT="/Users/niuyufei/ai-hedge-fund-2025"
LAUNCHER="$PROJECT_ROOT/scripts/macos_launcher.sh"

if [ ! -f "$LAUNCHER" ]; then
    /usr/bin/osascript -e "display alert \"AI Hedge Fund 启动失败\" message \"未找到启动脚本：\n$LAUNCHER\n请确认项目目录未被移动。\" as critical"
    exit 1
fi

exec /bin/bash "$LAUNCHER" "$@"
EOF

chmod +x "$EXECUTABLE"

# 6. Ad-hoc Codesign & Quarantine Removal
echo "Signing application bundle..."
xattr -cr "$TARGET_APP" 2>/dev/null || true
codesign --force --deep --sign - "$TARGET_APP" 2>/dev/null || true

# 7. Notify LaunchServices
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister"
if [ -x "$LSREGISTER" ]; then
    "$LSREGISTER" -u "$USER_TARGET_APP" 2>/dev/null || true
    "$LSREGISTER" -u "$DIST_APP" 2>/dev/null || true
    "$LSREGISTER" -f "$TARGET_APP" 2>/dev/null || true
fi

echo "=== Build and Installation Successful! ==="
echo "Official App Location: $TARGET_APP"
