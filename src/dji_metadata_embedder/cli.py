"""CLI entry point."""
import sys
from pathlib import Path

def main():
    print("DJI Metadata Embedder v1.0.2")
    print("Usage: dji-embed <input_directory>")
    if len(sys.argv) < 2:
        print("Error: Please provide an input directory")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    print(f"Processing directory: {input_path}")
    print("Note: Full implementation needs to be migrated.")

if __name__ == "__main__":
    main()
