from __future__ import annotations

import pytest

from app.config import Settings
from app.services.qa import GraphAnswerEngine
from app.services.snapshot import DEMO_VERSION, SnapshotManager


@pytest.fixture(scope="session")
def demo_context(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("vitak-data")
    settings = Settings(data_dir=data_dir, _env_file=None)
    settings.ensure_dirs()
    manager = SnapshotManager(settings)
    manager.create_demo_snapshot()
    manager.activate(DEMO_VERSION)
    context = manager.open(DEMO_VERSION)
    yield settings, manager, context
    context.close()


@pytest.fixture()
def engine(demo_context):
    settings, _, context = demo_context
    return GraphAnswerEngine(settings, context)
