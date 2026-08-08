"""Tests for services/staleness.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.staleness import mark_dependents_stale


@pytest.mark.asyncio
async def test_mark_dependents_stale_extracts_slugs_from_rows() -> None:
    artifact_id = uuid4()
    mock_response = MagicMock(data=[{"slug": "content-outline"}, {"slug": "content-script-s1"}])
    mock_rpc_builder = MagicMock()
    mock_rpc_builder.execute.return_value = mock_response
    mock_client = MagicMock()
    mock_client.rpc.return_value = mock_rpc_builder

    with patch("app.services.staleness.get_supabase", return_value=mock_client):
        result = await mark_dependents_stale(artifact_id, "outline changed")

    assert result == ["content-outline", "content-script-s1"]
    mock_client.rpc.assert_called_once_with(
        "mark_dependents_stale", {"p_artifact_id": str(artifact_id), "p_reason": "outline changed"}
    )


@pytest.mark.asyncio
async def test_mark_dependents_stale_empty_when_nothing_affected() -> None:
    artifact_id = uuid4()
    mock_response = MagicMock(data=[])
    mock_rpc_builder = MagicMock()
    mock_rpc_builder.execute.return_value = mock_response
    mock_client = MagicMock()
    mock_client.rpc.return_value = mock_rpc_builder

    with patch("app.services.staleness.get_supabase", return_value=mock_client):
        result = await mark_dependents_stale(artifact_id, "no dependents")

    assert result == []
