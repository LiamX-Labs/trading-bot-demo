#!/usr/bin/env python3
"""
CFT Prop Trading Bot - Restructured Version
Main entry point that uses the new modular architecture while maintaining all functionality.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import the new modular main
try:
    from src.main import main as restructured_main
except ImportError:
    print("❌ Error: Could not import restructured modules.")
    print("🔧 Make sure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

if __name__ == "__main__":
    print("🚀 Starting CFT Prop Trading Bot (Restructured Version)...")
    print("📁 Using new modular architecture...")
    
    try:
        asyncio.run(restructured_main())
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)