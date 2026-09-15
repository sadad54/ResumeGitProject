from proofhire_api.services.jd_fetch import clean_html_to_text


def test_strips_tags():
    html = "<html><body><h1>Backend Engineer</h1><p>2+ years Python</p></body></html>"
    result = clean_html_to_text(html)
    assert "<" not in result
    assert "Backend Engineer" in result
    assert "2+ years Python" in result


def test_strips_script_and_style_content():
    html = "<script>trackUser();</script><style>.a{color:red}</style><p>Real content</p>"
    result = clean_html_to_text(html)
    assert "trackUser" not in result
    assert "color:red" not in result
    assert "Real content" in result


def test_collapses_excess_whitespace():
    html = "<p>Line one</p>\n\n\n\n<p>Line two</p>"
    result = clean_html_to_text(html)
    assert "\n\n\n" not in result


def test_empty_html_returns_empty_string():
    assert clean_html_to_text("") == ""
