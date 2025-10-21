#!/bin/bash
# Safety Check - Verify V1 Backup Integrity
# Run this before making any destructive changes

echo "🔒 V1 Backup Safety Check"
echo "================================"
echo ""

BACKUP_DIR="/home/william/Desktop/cftprop/backtesting_backup"
ORIGINAL_DIR="/home/william/Desktop/cftprop/backtesting"

# Check if backup exists
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ CRITICAL: Backup directory not found!"
    echo "   Expected: $BACKUP_DIR"
    exit 1
fi

# Count files in backup
BACKUP_COUNT=$(find "$BACKUP_DIR" -type f -name "*.py" | wc -l)
echo "✅ Backup exists: $BACKUP_DIR"
echo "   Python files in backup: $BACKUP_COUNT"

# Verify key files exist
KEY_FILES=(
    "data_fetcher.py"
    "token_universe_scanner.py"
    "strategy_rules.py"
    "signal_generator.py"
    "pyramid_backtest.py"
    "run_interactive_backtest.py"
)

echo ""
echo "🔍 Checking critical files..."
MISSING=0
for file in "${KEY_FILES[@]}"; do
    if [ -f "$BACKUP_DIR/$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ MISSING: $file"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -gt 0 ]; then
    echo ""
    echo "❌ CRITICAL: $MISSING critical files missing from backup!"
    exit 1
fi

# Check backup timestamp
if [ -f "$BACKUP_DIR/BACKUP_INFO.txt" ]; then
    echo ""
    echo "📅 Backup Info:"
    cat "$BACKUP_DIR/BACKUP_INFO.txt"
fi

echo ""
echo "================================"
echo "✅ Backup verification PASSED"
echo "✅ Safe to proceed with V2 implementation"
echo ""
