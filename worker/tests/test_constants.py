from constants import SCRAPE_SLEEP


def test_scrape_sleep_is_positive():
    assert SCRAPE_SLEEP > 0
    assert isinstance(SCRAPE_SLEEP, int)
