"""Tests for the FastAPI REST API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(api_client):
    resp = await api_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_canonical_events(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_pagination(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events?page=1&size=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == 2
    assert data["pages"] == 2


@pytest.mark.asyncio
async def test_list_filter_by_city(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events?city=freiburg")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["location_city"] == "Freiburg"


@pytest.mark.asyncio
async def test_list_search_by_title(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events?q=Fasching")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert "Fasching" in data["items"][0]["title"]


@pytest.mark.asyncio
async def test_list_filter_by_date_range(api_client, seeded_db):
    resp = await api_client.get(
        "/api/canonical-events?date_from=2026-02-01&date_to=2026-03-01"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Fasching in Freiburg"


@pytest.mark.asyncio
async def test_list_filter_by_category(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events?category=stadtfest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Stadtfest Offenburg"


@pytest.mark.asyncio
async def test_detail_canonical_event(api_client, seeded_db):
    # First get the list to find the Fasching event ID
    list_resp = await api_client.get("/api/canonical-events?q=Fasching")
    event_id = list_resp.json()["items"][0]["id"]

    resp = await api_client.get(f"/api/canonical-events/{event_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Fasching in Freiburg"
    assert len(data["sources"]) == 2
    assert len(data["match_decisions"]) == 1


@pytest.mark.asyncio
async def test_detail_includes_source_dates(api_client, seeded_db):
    list_resp = await api_client.get("/api/canonical-events?q=Fasching")
    event_id = list_resp.json()["items"][0]["id"]

    resp = await api_client.get(f"/api/canonical-events/{event_id}")
    data = resp.json()
    # Each source event should have dates
    for source in data["sources"]:
        assert "dates" in source
        assert len(source["dates"]) >= 1
        assert "date" in source["dates"][0]


@pytest.mark.asyncio
async def test_detail_includes_match_scores(api_client, seeded_db):
    list_resp = await api_client.get("/api/canonical-events?q=Fasching")
    event_id = list_resp.json()["items"][0]["id"]

    resp = await api_client.get(f"/api/canonical-events/{event_id}")
    data = resp.json()
    md = data["match_decisions"][0]
    assert "title_score" in md
    assert "geo_score" in md
    assert "date_score" in md
    assert "description_score" in md
    assert md["combined_score"] == 0.85


@pytest.mark.asyncio
async def test_detail_not_found(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events/9999")
    assert resp.status_code == 404


# --- Phase 11 tests ---


@pytest.mark.asyncio
async def test_list_distinct_categories(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events/categories")
    assert resp.status_code == 200
    cats = resp.json()
    assert isinstance(cats, list)
    assert "fasching" in cats
    assert "karneval" in cats
    assert "stadtfest" in cats
    assert cats == sorted(cats)  # must be sorted alphabetically


@pytest.mark.asyncio
async def test_list_distinct_cities(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events/cities")
    assert resp.status_code == 200
    cities = resp.json()
    assert isinstance(cities, list)
    assert "Freiburg" in cities
    assert "Offenburg" in cities
    assert cities == sorted(cities)


@pytest.mark.asyncio
async def test_categories_route_not_matched_as_event_id(api_client, seeded_db):
    """Ensure /categories is NOT interpreted as GET /{event_id} with event_id='categories'."""
    resp = await api_client.get("/api/canonical-events/categories")
    # Must be 200 (list), NOT 422 (validation error for non-int event_id)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_multi_city_filter(api_client, seeded_db):
    resp = await api_client.get(
        "/api/canonical-events?city=Freiburg&city=Offenburg"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2  # both cities returned (OR semantics)


@pytest.mark.asyncio
async def test_list_multi_category_and_semantics(api_client, seeded_db):
    # Both fasching AND karneval -> only Fasching event has both
    resp = await api_client.get(
        "/api/canonical-events?category=fasching&category=karneval"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Fasching in Freiburg"


@pytest.mark.asyncio
async def test_list_sort_by_city_asc(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events?sort_by=city&sort_dir=asc")
    assert resp.status_code == 200
    data = resp.json()
    cities = [item["location_city"] for item in data["items"]]
    assert cities == sorted(cities)


@pytest.mark.asyncio
async def test_list_sort_by_city_desc(api_client, seeded_db):
    resp = await api_client.get("/api/canonical-events?sort_by=city&sort_dir=desc")
    assert resp.status_code == 200
    data = resp.json()
    cities = [item["location_city"] for item in data["items"]]
    assert cities == sorted(cities, reverse=True)


@pytest.mark.asyncio
async def test_list_size_200_accepted(api_client, seeded_db):
    """size=200 must not be rejected (previously capped at le=100)."""
    resp = await api_client.get("/api/canonical-events?size=200")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_size_10000_accepted(api_client, seeded_db):
    """size=10000 (ALL sentinel) must be accepted."""
    resp = await api_client.get("/api/canonical-events?size=10000")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
