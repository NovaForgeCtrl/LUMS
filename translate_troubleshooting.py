#!/usr/bin/env python3
import os

# Read source file
with open('./troubleshooting.md', 'r', encoding='utf-8') as f:
    source = f.read()

print("Translation script ready")
print("Source length:", len(source))
