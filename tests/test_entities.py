from nlu.entities import parse_location, parse_datetime, parse_units


def test_parse_location_city_state():
    assert parse_location("what's weather in Orlando Florida") == "Orlando, FL"


def test_parse_location_zip():
    assert parse_location("current temperature for 78705") == "78705"


def test_parse_location_none():
    assert parse_location("how are you?") is None


def test_parse_datetime_keywords():
    assert parse_datetime("tonight please") == "tonight"
    assert parse_datetime("tmrw forecast") == "tomorrow"
    assert parse_datetime("this weekend") == "weekend"
    assert parse_datetime("on Wednesday") == "wednesday"


def test_parse_datetime_default_today():
    assert parse_datetime("what's up") == "today"


def test_parse_units_metric_and_default():
    assert parse_units("in celsius") == "metric"
    assert parse_units("metric units please") == "metric"
    assert parse_units("fahrenheit") == "imperial"
    assert parse_units("no units mentioned") == "imperial"

