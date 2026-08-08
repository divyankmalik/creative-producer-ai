"""Tests for main.py's /health endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_when_db_reachable() -> None:
    mock_builder = MagicMock()
    mock_builder.execute.return_value = MagicMock(data=[])
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.limit.return_value = mock_builder

    with patch("app.main.get_supabase", return_value=mock_client):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_db_unreachable() -> None:
    mock_client = MagicMock()
    mock_client.table.side_effect = Exception("connection refused")

    with patch("app.main.get_supabase", return_value=mock_client):
        response = client.get("/health")

    assert response.status_code == 503
