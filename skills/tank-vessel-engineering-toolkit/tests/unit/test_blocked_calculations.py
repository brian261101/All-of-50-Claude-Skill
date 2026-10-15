from tankvessel.calculations.asme_viii_1 import shell_internal_pressure
from tankvessel.calculations.api_650 import shell_courses
from tankvessel.status import Status

def test_asme_calculation_fails_closed():
    result = shell_internal_pressure({"design_pressure": 100})
    assert result.status == Status.BLOCKED
    assert result.results == {}

def test_api_calculation_fails_closed():
    result = shell_courses({"design_pressure": 0})
    assert result.status == Status.BLOCKED
    assert result.results == {}
