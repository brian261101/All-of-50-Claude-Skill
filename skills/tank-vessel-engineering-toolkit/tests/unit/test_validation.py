from tankvessel.validation import validate_route, validate_positive_if_present

def test_asme_route_requires_edition_and_units():
    data = {"equipment": {"category": "PRESSURE_VESSEL"}, "code": {"family": "ASME_VIII_1"}, "project": {"units": "SI"}}
    assert validate_route(data) == ["Exact code edition is required; do not infer a default."]

def test_mismatched_route_is_rejected():
    data = {"equipment": {"category": "PRESSURE_VESSEL"}, "code": {"family": "API_650", "edition": "edition supplied"}, "project": {"units": "SI"}}
    errors = validate_route(data)
    assert any("unsupported" in e for e in errors)

def test_no_code_route_is_rejected():
    assert validate_route({})

def test_positive_validation():
    assert validate_positive_if_present({"conditions": {"design_pressure_kPa_g": 0}}, ["conditions.design_pressure_kPa_g"])
    assert not validate_positive_if_present({"conditions": {"design_pressure_kPa_g": 100}}, ["conditions.design_pressure_kPa_g"])
