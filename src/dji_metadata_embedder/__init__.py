"""DJI Drone Metadata Embedder."""
__version__ = "1.0.6"

# Import check to ensure files were moved correctly
try:
    from .embedder import DJIMetadataEmbedder, run_doctor
    from .per_frame_embedder import embed_flight_path, extract_frame_locations
    from .dat_parser import parse_v13 as parse_dat_v13
    from .cli import main

    __all__ = [
        "__version__",
        "main",
        "DJIMetadataEmbedder",
        "run_doctor",
        "embed_flight_path",
        "extract_frame_locations",
        "parse_dat_v13",
    ]
except ImportError as e:  # noqa: BLE001
    import warnings

    warnings.warn(f"Some modules could not be imported: {e}")
    __all__ = ["__version__"]
