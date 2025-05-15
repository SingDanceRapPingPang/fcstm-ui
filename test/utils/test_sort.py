import pytest

from app.utils import smart_sort


@pytest.mark.unittest
class TestUtilsSort:
    def test_smart_sort(self):
        assert smart_sort(['5', '1', '2', '4', '3', '-2.5', '3.0001', '10']) == \
               ['-2.5', '1', '2', '3', '3.0001', '4', '5', '10']
        assert smart_sort(['5', '1', '2', '4', '3', '-2.5', 'a', '10']) == \
               ['-2.5', '1', '10', '2', '3', '4', '5', 'a']
