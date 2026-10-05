"""Verify an existing Godot Web export; never regenerate or change game files."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def verify(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / "build-manifest.json").read_text(encoding="utf-8"))
    checked = []
    for record in manifest["files"]:
        name = record["path"]
        if ":" in name or "\\" in name or name.startswith("/") or ".." in PurePosixPath(name).parts:
            raise RuntimeError(f"Unsafe manifest path: {name}")
        file = folder / name
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(folder):
            raise RuntimeError(f"Missing or redirected build resource: {name}")
        data = file.read_bytes()
        if len(data) != record["size_bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise RuntimeError(f"Export integrity mismatch: {name}")
        if len(data) >= 100 * 1024 * 1024:
            raise RuntimeError(f"File exceeds GitHub's regular Git file limit: {name}")
        checked.append(name)
    required = ["index.html", "index.js", "index.wasm", "index.pck",
                "index.audio.worklet.js", "index.audio.position.worklet.js"]
    if not set(required).issubset(checked) or manifest["threads"]:
        raise RuntimeError("Incomplete or threaded export")
    html = (folder / "index.html").read_text(encoding="utf-8")
    config = json.loads(re.search(r"const GODOT_CONFIG\s*=\s*(\{.*?\});", html)[1])
    refs = re.findall(r'(?:src|href)=["\x27]([^"\x27]+)', html)
    refs += list(config["fileSizes"])
    refs += [config["executable"] + suffix for suffix in [".wasm", ".pck", ".audio.worklet.js", ".audio.position.worklet.js"]]
    names = {str(f.relative_to(folder)).replace("\\", "/") for f in folder.rglob("*") if f.is_file()}
    for ref in refs:
        if ref not in names or ref.startswith("/") or ":" in ref:
            raise RuntimeError(f"Non-relative, missing or case-mismatched resource: {ref}")
    return {"passed": True, "version": manifest["version"], "checked_files": checked,
            "project_pages_relative_resources": sorted(set(refs))}


if __name__ == "__main__":
    print(json.dumps(verify(sys.argv[1] if len(sys.argv) > 1 else "build/web"), indent=2))
