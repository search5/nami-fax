"""Multi-database safety: fail fast on schema errors."""

from __future__ import annotations

from unittest.mock import patch

import pytest


# --- schema initialisation must not fail silently ------------------------------------

def test_create_app_fails_fast_when_schema_initialisation_fails(tmp_path):
    from namifax import create_app

    with patch("namifax.db.bootstrap.upgrade_to_head", side_effect=OSError("disk is full")):
        with pytest.raises(RuntimeError, match="initiali[sz]ation failed"):
            create_app(**{"sqlalchemy.url": f"sqlite:///{tmp_path / 'x.db'}"})


def test_cli_session_fails_fast_when_schema_initialisation_fails(tmp_path):
    from namifax.db.provider import cli_session

    with patch("namifax.db.bootstrap.upgrade_to_head", side_effect=OSError("disk is full")):
        with pytest.raises(RuntimeError, match="initiali[sz]ation failed"):
            with cli_session(ensure_schema=True, environ={"DATABASE_URL": f"sqlite:///{tmp_path / 'y.db'}"}):
                pytest.fail("the block must not run")
