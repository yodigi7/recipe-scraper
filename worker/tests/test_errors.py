from errors import NotOKHttpResponse


def test_not_ok_http_response_is_exception():
    exc = NotOKHttpResponse("test error")
    assert isinstance(exc, Exception)
    assert str(exc) == "test error"
