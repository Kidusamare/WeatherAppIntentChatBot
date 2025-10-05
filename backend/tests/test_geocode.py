import pytest

pd = pytest.importorskip("pandas")

from backend.tools.geocode import geocode, _PROVIDER_INSTANCE


def test_local_geocode_with_csv(tmp_path, monkeypatch):
    # Prepare a small CSV for local geocoder
    csv = tmp_path / "us_places.csv"
    df = pd.DataFrame(
        {
            "USPS": ["TX", "MD"],
            "name": ["Austin city", "Baltimore city"],
            "lat": [30.2672, 39.2904],
            "long": [-97.7431, -76.6122],
        }
    )
    df.to_csv(csv, index=False)
    monkeypatch.setenv("US_PLACES_CSV", str(csv))
    # Clear singleton provider so the temp CSV is reloaded
    from tools import geocode as module

    module._PROVIDER_INSTANCE = None  # type: ignore[attr-defined]
    module._CACHE.clear()  # type: ignore[attr-defined]

    latlon = geocode("Austin, TX")
    assert latlon == (30.2672, -97.7431)

    # City-only: should still find a match via substring
    latlon2 = geocode("Austin")
    assert latlon2 == (30.2672, -97.7431)
