import pathlib
import os


CPACK_HOME = (
    pathlib.Path.home() / ".comfypack"
    if not os.environ.get("CPACK_HOME", "")
    else pathlib.Path(os.environ.get("CPACK_HOME", ""))
)
if not CPACK_HOME.exists():
    CPACK_HOME.mkdir()

MODEL_DIR = CPACK_HOME / "models"
WORKSPACE_DIR = CPACK_HOME / "workspace"
SHA_CACHE_FILE = CPACK_HOME / ".sha_cache.json"

COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"