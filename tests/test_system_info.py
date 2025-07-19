import sys

from dji_metadata_embedder.utils import system_info


def test_python_info():
    info = system_info.get_python_info()
    assert info["version"].startswith(str(sys.version_info.major))
    assert info["path"] == sys.executable


def test_disk_space(tmp_path):
    space = system_info.get_disk_space(tmp_path)
    assert isinstance(space, int) and space > 0


def test_system_architecture():
    arch = system_info.get_system_architecture()
    assert arch in {"32-bit", "64-bit"}


def test_system_summary_contains_keys():
    summary = system_info.get_system_summary()
    for key in {"windows_version", "python_version", "python_path", "architecture", "admin"}:
        assert key in summary
