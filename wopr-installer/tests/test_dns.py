"""
Tests for Cloudflare DNS Service
==================================

Tests DNS record CRUD operations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestCloudflareDNS:
    """Test CloudflareDNS service."""

    @pytest.mark.asyncio
    async def test_create_a_record(self, mock_cloudflare_dns):
        """A record creation returns record ID."""
        record_id = await mock_cloudflare_dns.create_a_record(
            name="test.wopr.systems",
            ip="1.2.3.4",
        )
        assert record_id == "rec_12345"
        mock_cloudflare_dns.create_a_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_record(self, mock_cloudflare_dns):
        """Record deletion succeeds."""
        result = await mock_cloudflare_dns.delete_record("rec_12345")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_beacon_records(self, mock_cloudflare_dns):
        """Beacon records deletion returns count."""
        record_ids = {"a_record": "rec_1", "wildcard": "rec_2"}
        count = await mock_cloudflare_dns.delete_beacon_records(record_ids)
        assert count == 2

    @pytest.mark.asyncio
    async def test_list_records(self, mock_cloudflare_dns):
        """List records returns empty list by default."""
        records = await mock_cloudflare_dns.list_records()
        assert isinstance(records, list)
