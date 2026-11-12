import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class AccessDenied(PermissionError):
    pass


def relative_path(value):
    if value == ".":
        return value
    path = PurePosixPath(value)
    if (not value or "\\" in value or ":" in value or path.is_absolute()
            or any(part in (".", "..", "") for part in value.split("/"))):
        raise AccessDenied("Invalid repository-relative path")
    return path.as_posix()


@dataclass(frozen=True)
class Scope:
    user: str
    repository: str
    root: Path
    prefixes: tuple[str, ...]

    @property
    def key(self):
        return hashlib.sha256(json.dumps(self.prefixes).encode()).hexdigest()

    def allows(self, path):
        path = relative_path(path)
        return any(prefix == "." or path == prefix or path.startswith(prefix + "/")
                   for prefix in self.prefixes)

    def resolve(self, path):
        if not self.allows(path):
            raise AccessDenied("Path not authorized")
        candidate = self.root / path
        if not candidate.resolve().is_relative_to(self.root):
            raise AccessDenied("Path escapes approved root")
        return candidate


class Permissions:
    def __init__(self, config):
        self.config = config

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def identity(self, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        user = next((identity for stored, identity in self.config.get("credentials", {}).items()
                     if hmac.compare_digest(stored, digest)), None)
        if user is None or not token:
            raise AccessDenied("Unknown credential")
        return user

    def authorize(self, token, repository):
        user = self.identity(token)
        registered = self.config.get("repositories", {}).get(repository)
        prefixes = registered.get("users", {}).get(user, []) if registered else []
        if not prefixes:
            raise AccessDenied("Repository not authorized")
        # Filesystem resolution happens only after identity/repository permission.
        root = Path(registered["root"])
        if not root.is_absolute():
            raise ValueError("Registered roots must be absolute")
        root = root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Registered root is not a directory")
        return Scope(user, repository, root, tuple(sorted({relative_path(p) for p in prefixes})))
