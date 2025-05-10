#!/bin/bash
set -e

ADDON_NAME="answer_eval"
BUILD_DIR="build"
ADDON_DIR="$BUILD_DIR/$ADDON_NAME"

# Clean build dir
rm -rf "$BUILD_DIR"
mkdir -p "$ADDON_DIR"

# Copy necessary files
cp __init__.py manifest.json config.json README.md "$ADDON_DIR/"

# Create the zip with files at the root (not inside a folder)
cd "$ADDON_DIR"
zip -r "../../${ADDON_NAME}.ankiaddon" *
cd ../..
rm -rf "$BUILD_DIR"

echo "Addon packaged as ${ADDON_NAME}.ankiaddon (files at archive root)"