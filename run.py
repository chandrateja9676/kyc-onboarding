#!/usr/bin/env python3
"""
Main launcher script for the KYC Onboarding & Evidence Lifecycle Platform.
Usage:
    python run.py generate [--profile starter|standard|full] [--seed 20261022]
    python run.py validate
    python run.py reproduce
    python run.py serve [--port 8080]
    python run.py all
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli import main

if __name__ == "__main__":
    main()
