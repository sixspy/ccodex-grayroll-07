"""grayroll-07 测试隔离：每个用例前重置为种子库，杜绝共享 data/app.db 串测。"""
from pathlib import Path

import pytest

from db import DB_PATH, init_db


@pytest.fixture(autouse=True)
def _reset_db():
    Path(DB_PATH).unlink(missing_ok=True)
    init_db()
    yield
