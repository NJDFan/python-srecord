try:
    import importlib.metadata
    __version__ = importlib.metadata.version(__package__)
except ImportError:
    try:
        import pkg_resources
        __version__ = pkg_resources.get_distribution(__package__).version
    except ImportError:
        __version__ = 'unknown'

__all__ = ["transform", "checksum", "input", "output", "generator", "settings"]
