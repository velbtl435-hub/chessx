"""Optional dependency loader with clear error messages."""


class MissingDependency(ImportError):
    pass


def need_numpy():
    try:
        import numpy
        return numpy
    except ImportError as e:
        raise MissingDependency("chessx_libs.media.gen.audio needs numpy: pip install numpy") from e


def need_pil():
    try:
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont
    except ImportError as e:
        raise MissingDependency("chessx_libs.media.gen image/gif need Pillow: pip install pillow") from e
