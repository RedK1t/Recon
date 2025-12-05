#!/usr/bin/env python3
"""
Deduplicate wordlist files - removes duplicate entries while preserving order
"""

import os

# List of wordlist files to deduplicate
WORDLIST_FILES = [
    "top1k.txt",
    "top10k.txt",
    "top25k.txt",
    "top50k.txt",
    "top100k.txt"
]

def deduplicate_file(filepath):
    """
    Remove duplicate lines from a file while preserving order
    
    Args:
        filepath: Path to the file to deduplicate
    """
    if not os.path.exists(filepath):
        print(f"⚠️  File not found: {filepath}")
        return
    
    print(f"Processing: {filepath}")
    
    # Read all lines
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    original_count = len(lines)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_lines = []
    duplicates_removed = 0
    
    for line in lines:
        # Normalize the line (strip whitespace for comparison)
        normalized = line.strip()
        
        # Skip empty lines and comments
        if not normalized or normalized.startswith('#'):
            unique_lines.append(line)
            continue
        
        # Check if we've seen this line before
        if normalized.lower() not in seen:
            seen.add(normalized.lower())
            unique_lines.append(line)
        else:
            duplicates_removed += 1
    
    # Write back to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(unique_lines)
    
    final_count = len(unique_lines)
    
    print(f"  ✓ Original: {original_count} lines")
    print(f"  ✓ Duplicates removed: {duplicates_removed}")
    print(f"  ✓ Final: {final_count} unique lines")
    print()

def main():
    print("=" * 60)
    print("Wordlist Deduplication Tool")
    print("=" * 60)
    print()
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    total_duplicates = 0
    
    for filename in WORDLIST_FILES:
        filepath = os.path.join(script_dir, filename)
        deduplicate_file(filepath)
    
    print("=" * 60)
    print("✓ Deduplication complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
