"""Pytest plugin to ensure project root is in sys.path before test collection"""
import sys
from pathlib import Path

# Add project root to sys.path at plugin load time (before assertion rewriting)
_root = Path(__file__).resolve().parent
_root_str = str(_root)
_parent_str = str(_root.parent)

# Remove parent directory if it's in sys.path (it interferes with imports)
if _parent_str in sys.path:
    sys.path.remove(_parent_str)

# Ensure project root is at the beginning of sys.path
if _root_str in sys.path:
    sys.path.remove(_root_str)
sys.path.insert(0, _root_str)

# Re-add parent at the end if needed (for aitext package)
if _parent_str not in sys.path:
    sys.path.append(_parent_str)


def pytest_configure(config):
    """Ensure paths are set before test collection"""
    # Double-check that project root is first in sys.path
    if _root_str in sys.path:
        sys.path.remove(_root_str)
    sys.path.insert(0, _root_str)
