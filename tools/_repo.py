"""Locate the repository from any script in tools/ and put its packages on sys.path.

Why this exists
---------------
Every script in this directory used to live in backend/scripts/ and climbed out of it with
its own ``os.path.dirname(os.path.dirname(__file__))``. That works until the directory moves,
and then it fails silently: the import resolves to nothing, or to a stale installed copy. When
the development scripts were separated from the operating scripts on 2026-09-04, this file
became the one place that knows where ``backend/`` is relative to ``tools/``.

Use
---
At the top of a script in tools/::

    from _repo import BACKEND, ROOT     # also puts backend/ and services/*/src on sys.path

or just ``import _repo`` when only the side effect is wanted. Scripts one level down, in
tools/oneshot/, put this directory on the path first::

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from _repo import BACKEND

``backend/cfr_dispatch/__init__.py`` also injects the services paths at import time
(CLAUDE.md §2); adding them here as well means a script that imports ``gis_service`` directly,
without ``cfr_dispatch``, still resolves.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SERVICES = ROOT / "services"


def _add(path: Path) -> None:
    text = str(path)
    if path.is_dir() and text not in sys.path:
        sys.path.insert(0, text)


# Inserted in reverse priority so that backend/ ends up first.
for _p in (SERVICES / "dispatch_notifications" / "src",
           SERVICES / "audio_analysis" / "src",
           SERVICES / "gis" / "src",
           BACKEND):
    _add(_p)
