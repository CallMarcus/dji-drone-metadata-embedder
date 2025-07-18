cd C:\Claude\dji-drone-metadata-embedder

# Create directory structure
# mkdir -p src\dji_metadata_embedder

# Create __init__.py
@'
"""DJI Drone Metadata Embedder."""
__version__ = "1.0.3"
from .cli import main
__all__ = ["main", "__version__"]
'@ | Out-File -FilePath "src\dji_metadata_embedder\__init__.py" -Encoding UTF8

# Create cli.py  
@'
"""CLI entry point."""
import sys
from pathlib import Path

def main():
    print("DJI Metadata Embedder v1.0.3")
    print("Usage: dji-embed <input_directory>")
    if len(sys.argv) < 2:
        print("Error: Please provide an input directory")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    print(f"Processing directory: {input_path}")
    print("Note: Full implementation needs to be migrated.")

if __name__ == "__main__":
    main()
'@ | Out-File -FilePath "src\dji_metadata_embedder\cli.py" -Encoding UTF8