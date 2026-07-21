from pathlib import Path

DEFAULT_MODEL = "ViT-B-32"
DEFAULT_CACHE_DIR = Path(".eas_cache")
DEFAULT_THRESHOLD = 0.45
DEFAULT_TOP_N = 20
DEFAULT_OUTPUT_DIR = Path("output")

SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"}
BATCH_SIZE = 32
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
