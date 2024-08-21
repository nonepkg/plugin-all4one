import importlib.metadata as importlib_metadata

# from importlib.resources import read_text


def read_version() -> str:
    try:
        return importlib_metadata.version(__package__ or "nonebot_plugin_all4one")
    except importlib_metadata.PackageNotFoundError:
        return "0.1.0"
        # return read_text("nonebot_plugin_all4one", "VERSION").strip()


__version__ = read_version()
