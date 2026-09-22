"""DJI Drone Metadata Embedder."""

__version__ = "2.16.1"

# Import check to ensure files were moved correctly
try:
    from .cli import main
    from .dat_parser import parse_v13 as parse_dat_v13
    from .embedder import DJIMetadataEmbedder, run_doctor
    from .per_frame_embedder import embed_flight_path, extract_frame_locations

    __all__ = [
        "DJIMetadataEmbedder",
        "__version__",
        "embed_flight_path",
        "extract_frame_locations",
        "main",
        "parse_dat_v13",
        "run_doctor",
    ]
except ImportError as e:
    import warnings

    warnings.warn(f"Some modules could not be imported: {e}")
    __all__ = ["__version__"]
