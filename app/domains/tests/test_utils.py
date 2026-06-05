from domains.utils import reverse_fqdn


def test_reverse_fqdn_subdomain():
    assert reverse_fqdn("api.dev.example.co.jp") == "jp.co.example.dev.api"


def test_reverse_fqdn_registered_domain():
    assert reverse_fqdn("example.co.jp") == "jp.co.example"


def test_reverse_fqdn_single_label():
    assert reverse_fqdn("localhost") == "localhost"


def test_reverse_fqdn_trailing_dot_stripped():
    assert reverse_fqdn("example.co.jp.") == "jp.co.example"


def test_reverse_fqdn_gtld():
    assert reverse_fqdn("example.com") == "com.example"
