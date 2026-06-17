"""resolve_package_url 单元测试。"""

from backend.utils.package_url import resolve_package_url

_TEMPLATE = (
    "https://example.com/path?branch=code_branch&time=start_time&pkg=package_name"
)


def test_mac_platform_builds_url():
    url, hint = resolve_package_url(
        _TEMPLATE,
        "mac.pkg",
        "oh.pkg",
        "master",
        "2026_0110_1200",
        "MAC",
    )
    assert hint is None
    assert url == "https://example.com/path?branch=master&time=202601101200&pkg=mac.pkg"


def test_oh_platform_builds_url():
    url, hint = resolve_package_url(
        _TEMPLATE,
        "mac.pkg",
        "oh.hap",
        "930bugfix",
        "202601211000",
        "oh",
    )
    assert hint is None
    assert url == "https://example.com/path?branch=930bugfix&time=202601211000&pkg=oh.hap"


def test_unknown_platform():
    url, hint = resolve_package_url(
        _TEMPLATE,
        "mac.pkg",
        "oh.pkg",
        "master",
        "202601211000",
        "android",
    )
    assert url is None
    assert hint == "unknown_platform"


def test_missing_config_or_fields():
    assert resolve_package_url("", "a", "b", "master", "t", "mac") == (None, None)
    assert resolve_package_url(_TEMPLATE, "", "b", "master", "t", "mac") == (None, None)
    assert resolve_package_url(_TEMPLATE, "a", "b", "", "t", "mac") == (None, None)
    assert resolve_package_url(_TEMPLATE, "a", "b", "master", "", "mac") == (None, None)
