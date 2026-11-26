"""Atomic persistent state store for published epochs and candidates."""

import os
import re
import tempfile
from typing import Optional, Tuple

from oracle.src.rewards.epoch_json import parse_epoch_json
from oracle.src.rewards.types import EpochJson

_PUBLISHED_FILE_RE = re.compile(r"^epoch_(\d+)\.json$")
_CANDIDATE_FILE_RE = re.compile(r"^epoch_(\d+)_.*\.json$")


class RewardsStateStore:
    """Manages `<state_dir>/published/` and `<state_dir>/candidates/` atomically."""

    def __init__(self, state_dir: str):
        if not state_dir:
            raise ValueError("REWARDS_STATE_DIR must be configured")
        self.state_dir = state_dir
        self.published_dir = os.path.join(state_dir, "published")
        self.candidates_dir = os.path.join(state_dir, "candidates")

    def ensure_dirs(self) -> None:
        os.makedirs(self.published_dir, exist_ok=True)
        os.makedirs(self.candidates_dir, exist_ok=True)

    def published_path(self, epoch: int) -> str:
        return os.path.join(self.published_dir, f"epoch_{int(epoch)}.json")

    def candidate_path(self, epoch: int, snapshot_block: int, snapshot_block_hash: str) -> str:
        clean_hash = snapshot_block_hash[2:] if snapshot_block_hash.startswith("0x") else snapshot_block_hash
        prefix = clean_hash[:12].lower()
        return os.path.join(
            self.candidates_dir, f"epoch_{int(epoch)}_{int(snapshot_block)}_{prefix}.json"
        )

    @staticmethod
    def write_atomic(target_path: str, raw_bytes: bytes) -> str:
        parent = os.path.dirname(target_path)
        os.makedirs(parent, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, target_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise
        return target_path

    def save_published(self, epoch: int, raw_bytes: bytes, prune: bool = True) -> str:
        path = self.write_atomic(self.published_path(epoch), raw_bytes)
        if prune:
            self.prune_published(keep_epoch=int(epoch))
            self.prune_candidates(up_to_epoch=int(epoch))
        return path

    def save_candidate(
        self,
        epoch: int,
        snapshot_block: int,
        snapshot_block_hash: str,
        raw_bytes: bytes,
        prune: bool = True,
    ) -> str:
        path = self.write_atomic(
            self.candidate_path(epoch, snapshot_block, snapshot_block_hash), raw_bytes
        )
        if prune:
            self.prune_candidates(up_to_epoch=int(epoch), keep_path=path)
        return path

    def prune_published(self, keep_epoch: int) -> None:
        """Remove older published epoch JSONs, retaining only `epoch_<keep_epoch>.json`."""
        if not os.path.isdir(self.published_dir):
            return
        keep_name = f"epoch_{int(keep_epoch)}.json"
        for name in os.listdir(self.published_dir):
            if name == keep_name:
                continue
            if _PUBLISHED_FILE_RE.match(name):
                try:
                    os.unlink(os.path.join(self.published_dir, name))
                except OSError:
                    pass

    def prune_candidates(
        self, up_to_epoch: Optional[int] = None, keep_path: Optional[str] = None
    ) -> None:
        """Remove obsolete candidate JSON files up to `up_to_epoch` (or all if None)."""
        if not os.path.isdir(self.candidates_dir):
            return
        keep_norm = os.path.abspath(keep_path) if keep_path else None
        for name in os.listdir(self.candidates_dir):
            match = _CANDIDATE_FILE_RE.match(name)
            if not match:
                continue
            full_path = os.path.abspath(os.path.join(self.candidates_dir, name))
            if keep_norm and full_path == keep_norm:
                continue
            file_epoch = int(match.group(1))
            if up_to_epoch is None or file_epoch <= int(up_to_epoch):
                try:
                    os.unlink(full_path)
                except OSError:
                    pass

    def load_published(self, epoch: int) -> Optional[Tuple[EpochJson, bytes, str]]:
        path = self.published_path(epoch)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as handle:
            raw = handle.read()
        return parse_epoch_json(raw), raw, path

    def load_candidate(
        self, epoch: int, snapshot_block: int, snapshot_block_hash: str
    ) -> Optional[Tuple[EpochJson, bytes, str]]:
        path = self.candidate_path(epoch, snapshot_block, snapshot_block_hash)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as handle:
            raw = handle.read()
        return parse_epoch_json(raw), raw, path
