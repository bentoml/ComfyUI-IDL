from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from .hash import get_sha256
from pathlib import Path
from .const import MODEL_DIR, COMFYUI_REPO


def _clone_commit(url: str, commit: str, dir: Path, verbose: int = 0):
    stdout = None if verbose > 0 else subprocess.DEVNULL
    stderr = None if verbose > 1 else subprocess.DEVNULL
    subprocess.check_call(
        ["git", "clone", "--recurse-submodules", "--filter=blob:none", url, dir],
        stdout=stdout,
        stderr=stderr,
    )
    subprocess.check_call(
        ["git", "fetch", "-q", url, commit],
        cwd=dir,
        stdout=stdout,
        stderr=stderr,
    )
    subprocess.check_call(
        ["git", "checkout", "FETCH_HEAD"],
        cwd=dir,
        stdout=stdout,
        stderr=stderr,
    )
    subprocess.check_call(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=dir,
        stdout=stdout,
        stderr=stderr,
    )


def install_comfyui(snapshot, workspace: Path, verbose: int = 0):
    print("Installing ComfyUI")
    comfyui_commit = snapshot["comfyui"]
    if workspace.exists():
        if workspace.joinpath(".DONE").exists():
            commit = (workspace / ".DONE").read_text()
            if commit.strip() == comfyui_commit:
                print("ComfyUI is already installed")
                return
        shutil.rmtree(workspace)
    _clone_commit(COMFYUI_REPO, comfyui_commit, workspace, verbose=verbose)
    with open(workspace / ".DONE", "w") as f:
        f.write(comfyui_commit)


def install_custom_modules(snapshot, workspace: Path, verbose: int = 0):
    print("Installing custom nodes")
    for module in snapshot["custom_nodes"]:
        url = module["url"]
        directory = url.split("/")[-1].split(".")[0]
        module_dir = workspace / "custom_nodes" / directory

        if module_dir.exists():
            if module_dir.joinpath(".DONE").exists():
                commit = (module_dir / ".DONE").read_text()
                if commit.strip() == module["commit_hash"]:
                    print(f"{directory} is already installed")
                    continue
            shutil.rmtree(module_dir)

        commit_hash = module["commit_hash"]
        _clone_commit(url, commit_hash, module_dir, verbose=verbose)

        if module_dir.joinpath("install.py").exists():
            venv = workspace / ".venv"
            if venv.exists():
                python = (
                    venv / "Scripts" / "python.exe"
                    if os.name == "nt"
                    else venv / "bin" / "python"
                )
            else:
                python = Path(sys.executable)
            subprocess.check_call(
                [str(python.absolute()), "install.py"],
                cwd=module_dir,
                stdout=subprocess.DEVNULL if verbose == 0 else None,
            )

        with open(module_dir / ".DONE", "w") as f:
            f.write(commit_hash)


def install_dependencies(
    snapshot: dict,
    req_file: str,
    workspace: Path,
    verbose: int = 0,
):
    if verbose > 0:
        print("Installing Python dependencies")
    python_version = snapshot["python"]
    stdout = None if verbose > 0 else subprocess.DEVNULL
    stderr = None if verbose > 1 else subprocess.DEVNULL

    subprocess.check_call(
        ["uv", "python", "install", python_version],
        cwd=workspace,
        stdout=stdout,
        stderr=stderr,
    )
    venv = workspace / ".venv"
    if (venv / "DONE").exists():
        return
    venv_py = (
        venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
    )
    subprocess.check_call(
        [
            "uv",
            "venv",
            "--python",
            python_version,
            venv,
        ],
        stdout=stdout,
        stderr=stderr,
    )
    subprocess.check_call(
        [
            "uv",
            "pip",
            "install",
            "-p",
            str(venv_py),
            "pip",
        ],
        stdout=stdout,
        stderr=stderr,
    )
    subprocess.check_call(
        [
            "uv",
            "pip",
            "install",
            "-p",
            str(venv_py),
            "-r",
            req_file,
            "--no-deps",
        ],
        stdout=stdout,
        stderr=stderr,
    )
    with open(venv / "DONE", "w") as f:
        f.write("DONE")
    return venv_py


def get_google_search_url(sha: str) -> tuple[str, str]:
    """Generate Google custom search URLs for model on HuggingFace and CivitAI"""
    base_url = "https://www.google.com/search"
    sha = sha.upper()
    hf_query = f"site:huggingface.co {sha}"
    civit_query = f"site:civitai.com {sha}"
    return (f"{base_url}?q={hf_query}", f"{base_url}?q={civit_query}")


def download_file(url: str, dest_path: Path, progress_callback=None):
    """Download file with progress tracking"""
    try:
        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get("content-length", 0))
            block_size = 8192
            downloaded = 0

            with open(dest_path, "wb") as f:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    f.write(buffer)
                    if progress_callback:
                        progress = (
                            (downloaded / total_size) * 100 if total_size > 0 else 0
                        )
                        progress_callback(progress)
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def show_progress(filename: str):
    """Progress callback function"""

    def callback(progress):
        print(f"\rDownloading {filename}: {progress:.1f}%", end="")

    return callback


def create_model_symlink(global_path: Path, sha: str, target_path: Path, filename: str):
    """Create symlink from global storage to workspace"""
    source = global_path / sha
    target = target_path / filename

    if target.exists():
        if target.is_symlink():
            target.unlink()
        else:
            raise RuntimeError(f"File {target} already exists and is not a symlink")

    target.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(source, target)


def retrive_models(
    snapshot: dict,
    workspace: Path,
    download: bool = True,
    verbose: int = 0,
):
    """Retrieve models from user downloads"""
    models = snapshot.get("models", [])
    if not models:
        return

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    for model in models:
        sha = model["sha256"]
        filename = model["filename"]
        disabled = model.get("disabled", False)
        if (workspace / filename).exists():
            if not (MODEL_DIR / sha).exists() and (workspace / filename).is_file():
                shutil.move(workspace / filename, MODEL_DIR / sha)
                create_model_symlink(MODEL_DIR, sha, workspace, filename)
            continue

        if (MODEL_DIR / sha).exists():
            print(f"Model {filename} already exists in cache")
            create_model_symlink(MODEL_DIR, sha, workspace, filename)
            continue

        if disabled:
            continue

        if not download:
            continue

        print(f"\nPlease download model: {filename}")
        hf_url, civit_url = get_google_search_url(sha)
        print(f"HuggingFace Search URL: {hf_url}")
        print(f"CivitAI Search URL: {civit_url}")

        while True:
            path = input("Enter path to downloaded file (or 'skip' to skip): ")
            if path.lower() == "skip":
                break

            try:
                # Check if input is a URL
                if path.startswith(("http://", "https://")):
                    url = path
                    target_path = MODEL_DIR / sha

                    # Start download in a separate thread
                    download_thread = threading.Thread(
                        target=download_file,
                        args=(url, target_path, show_progress(filename)),
                    )
                    download_thread.start()
                    download_thread.join()

                    if not target_path.exists():
                        print("\nDownload failed!")
                        continue

                    print("\nDownload completed! Verifying SHA256...")
                    terget_sha = get_sha256(str(target_path))
                    if terget_sha != sha:
                        print(
                            "SHA256 verification failed! File may be corrupted or incorrect."
                        )
                        target_path.unlink()
                        continue

                    print("SHA256 verification successful!")
                else:
                    # Handle local file
                    downloaded_path = Path(path)
                    if not downloaded_path.exists():
                        print("File does not exist!")
                        continue

                    # Verify SHA256 before copying
                    print("Verifying SHA256...")
                    target_sha = get_sha256(str(downloaded_path))
                    if target_sha != sha:
                        print(
                            f"Downloaded file SHA256 does not match expected SHA256: {target_sha} != {sha}"
                        )
                        continue

                    print("SHA256 verification successful!")
                    # Copy to global storage
                    shutil.copy2(downloaded_path, MODEL_DIR / sha)

                # Create symlink
                create_model_symlink(MODEL_DIR, sha, workspace, filename)
                print(f"Model {filename} installed successfully")
                break
            except Exception as e:
                print(f"Error processing file: {e}")
                continue


def install(cpack: str | Path, workspace: str | Path = "workspace", verbose: int = 0):
    workspace = Path(workspace)
    with tempfile.TemporaryDirectory() as temp_dir:
        pack_dir = Path(temp_dir) / ".cpack"
        shutil.unpack_archive(cpack, pack_dir)
        snapshot = json.loads((pack_dir / "snapshot.json").read_text())
        req_txt_file = pack_dir / "requirements.txt"

        install_comfyui(snapshot, workspace, verbose=verbose)
        install_dependencies(snapshot, str(req_txt_file), workspace, verbose=verbose)

        for f in (pack_dir / "input").glob("*"):
            if f.is_file():
                shutil.copy(f, workspace / "input" / f.name)
            elif f.is_dir():
                shutil.copytree(f, workspace / "input" / f.name, dirs_exist_ok=True)

        retrive_models(snapshot, workspace, verbose=verbose, download=False)

        install_custom_modules(snapshot, workspace, verbose=verbose)

        retrive_models(snapshot, workspace, verbose=verbose)
