"""Record an offline, exact transitive dependency lock from installed distributions.

This is the design's pip+lock alternative, not a claim that wheels are cached.
It never accesses a network or records environment variables.
"""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import tomllib
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def main():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    queue = project["project"]["dependencies"] + project["dependency-groups"]["dev"]
    resolved = {}
    while queue:
        req = Requirement(queue.pop())
        if req.marker and not req.marker.evaluate({"extra": ""}):
            continue
        name = canonicalize_name(req.name)
        dist = metadata.distribution(name)
        if dist.version not in req.specifier:
            raise RuntimeError(f"Installed version fails requirement for {name}")
        if name in resolved:
            continue
        record = dist.read_text("RECORD") or ""
        resolved[name] = {"version": dist.version, "installed_record_sha256": hashlib.sha256(record.encode()).hexdigest()}
        queue.extend(dist.requires or [])
    lines = ["# Offline observed dependency lock for Python " + platform.python_version() + " on " + platform.system(),
             "# Install with pip --no-index --find-links <wheelhouse> -r requirements.lock when wheels are supplied."]
    lines += [f"{name}=={resolved[name]['version']}" for name in sorted(resolved)]
    (ROOT / "requirements.lock").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    lock = {"python": platform.python_version(), "platform": platform.system(),
            "lock_method": "offline installed transitive dependency metadata", "network_used": False,
            "fresh_install_verified": False, "wheelhouse_available": False,
            "packages": dict(sorted(resolved.items()))}
    (ROOT / "research/environment.lock.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"packages_locked": len(resolved), "network_used": False, "fresh_install_verified": False}))


if __name__ == "__main__":
    main()
