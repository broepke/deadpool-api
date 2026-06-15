"""Shared test fixtures.

The reporting/picks services use module-global in-memory caches. Clear them
around every test so cached results from one test can't leak into another.
"""
import pytest

from src.utils.caching import reporting_cache, next_drafter_cache


@pytest.fixture(autouse=True)
def clear_caches():
    reporting_cache._cache.clear()
    next_drafter_cache._cache.clear()
    yield
    reporting_cache._cache.clear()
    next_drafter_cache._cache.clear()
