import pandas as pd
from tools.geocode import geocode


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

    latlon = geocode("Austin, TX")
    assert latlon == (30.2672, -97.7431)

    # City-only: should still find a match via substring
    latlon2 = geocode("Austin")
    assert latlon2 == (30.2672, -97.7431)
