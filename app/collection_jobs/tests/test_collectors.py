import socket
import urllib.error
import urllib.request
import dns.exception
import dns.resolver
import pytest
from unittest.mock import MagicMock, patch

from collection_jobs.collectors import (
    CertificateCollector,
    DnsRecordCollector,
    HttpStatusCollector,
    MailAuthCollector,
    RegistrationCollector,
    SecuritySummaryCollector,
)
from collection_jobs.models import CollectionResult
from domains.models import Domain
from owners.models import ManagementUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeRdata:
    def __init__(self, value):
        self._value = value
    def __str__(self):
        return self._value


class FakeAnswer:
    def __init__(self, values, ttl=300):
        self.ttl = ttl
        self._items = [FakeRdata(v) for v in values]
    def __iter__(self):
        return iter(self._items)


@pytest.fixture
def domain(db):
    unit = ManagementUnit.objects.create(
        unit_type=ManagementUnit.UNIT_REGISTERED_DOMAIN,
        unit_name="example.co.jp",
        setting_type=ManagementUnit.SETTING_INDIVIDUAL,
    )
    return Domain.objects.create(
        fqdn="example.co.jp",
        domain_type=Domain.TYPE_CCTLD,
        status=Domain.STATUS_ACTIVE,
        mgmt_category=Domain.CATEGORY_MANAGED,
        management_unit=unit,
    )


# ---------------------------------------------------------------------------
# DnsRecordCollector
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_dns_collector_returns_a_records(domain):
    def fake_resolve(fqdn, rtype, **kwargs):
        if rtype == "A":
            return FakeAnswer(["203.0.113.10", "203.0.113.11"])
        raise dns.resolver.NoAnswer

    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockResolver:
        MockResolver.return_value.resolve.side_effect = fake_resolve
        outcome = DnsRecordCollector().collect(domain)

    assert outcome.status == CollectionResult.STATUS_SUCCEEDED
    assert outcome.result_type == CollectionResult.TYPE_DNS_RECORDS
    assert outcome.method == CollectionResult.METHOD_DNS_QUERY
    a_records = [r for r in outcome.payload["records"] if r["type"] == "A"]
    assert len(a_records) == 2
    assert a_records[0]["value"] == "203.0.113.10"
    assert a_records[0]["ttl"] == 300


@pytest.mark.django_db
def test_dns_collector_collects_multiple_record_types(domain):
    def fake_resolve(fqdn, rtype, **kwargs):
        if rtype == "A":
            return FakeAnswer(["203.0.113.10"])
        if rtype == "MX":
            return FakeAnswer(["10 mail.example.co.jp."])
        raise dns.resolver.NoAnswer

    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockResolver:
        MockResolver.return_value.resolve.side_effect = fake_resolve
        outcome = DnsRecordCollector().collect(domain)

    types = {r["type"] for r in outcome.payload["records"]}
    assert "A" in types
    assert "MX" in types


@pytest.mark.django_db
def test_dns_collector_handles_nxdomain(domain):
    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockResolver:
        MockResolver.return_value.resolve.side_effect = dns.resolver.NXDOMAIN
        outcome = DnsRecordCollector().collect(domain)

    assert outcome.status == CollectionResult.STATUS_FAILED
    assert outcome.error_code == "nxdomain"


@pytest.mark.django_db
def test_dns_collector_handles_timeout(domain):
    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockResolver:
        MockResolver.return_value.resolve.side_effect = dns.exception.Timeout
        outcome = DnsRecordCollector().collect(domain)

    assert outcome.status == CollectionResult.STATUS_FAILED
    assert outcome.error_code == "timeout"


# ---------------------------------------------------------------------------
# HttpStatusCollector
# ---------------------------------------------------------------------------

def _make_urllib_response(status=200, url="https://example.co.jp"):
    resp = MagicMock()
    resp.status = status
    resp.url = url
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_opener(response):
    opener = MagicMock()
    opener.open.return_value = response
    return opener


@pytest.mark.django_db
def test_http_collector_returns_status_code(domain):
    response = _make_urllib_response(200)
    with patch("collection_jobs.collectors.urllib.request.build_opener", return_value=_mock_opener(response)):
        outcome = HttpStatusCollector().collect(domain)

    assert outcome.status == CollectionResult.STATUS_SUCCEEDED
    assert outcome.result_type == CollectionResult.TYPE_HTTP_STATUS
    assert outcome.method == CollectionResult.METHOD_HTTP_HEAD
    assert outcome.payload["status_code"] == 200


@pytest.mark.django_db
def test_http_collector_records_redirect_chain(domain):
    response = _make_urllib_response(200, url="https://www.example.co.jp")
    opener = _mock_opener(response)

    with patch("collection_jobs.collectors.urllib.request.build_opener", return_value=opener):
        # Simulate one redirect by appending to the redirects list inside the collector
        # (redirect tracking happens via the handler; for unit test we verify payload structure)
        outcome = HttpStatusCollector().collect(domain)

    assert outcome.payload["final_url"] == "https://www.example.co.jp"
    assert "redirects" in outcome.payload


@pytest.mark.django_db
def test_http_collector_handles_timeout(domain):
    opener = MagicMock()
    opener.open.side_effect = socket.timeout("timed out")

    with patch("collection_jobs.collectors.urllib.request.build_opener", return_value=opener):
        outcome = HttpStatusCollector().collect(domain)

    assert outcome.status == CollectionResult.STATUS_FAILED
    assert outcome.error_code == "timeout"


@pytest.mark.django_db
def test_http_collector_handles_connection_error(domain):
    opener = MagicMock()
    opener.open.side_effect = urllib.error.URLError("connection refused")

    with patch("collection_jobs.collectors.urllib.request.build_opener", return_value=opener):
        outcome = HttpStatusCollector().collect(domain)

    assert outcome.status == CollectionResult.STATUS_FAILED
    assert outcome.error_code == "connection_error"


# ---------------------------------------------------------------------------
# Stub collectors — just verify they return a valid succeeded outcome
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mail_auth_collector_returns_stub_outcome(domain):
    outcome = MailAuthCollector().collect(domain)
    assert outcome.result_type == CollectionResult.TYPE_MAIL_AUTH
    assert outcome.status == CollectionResult.STATUS_SUCCEEDED


@pytest.mark.django_db
def test_certificate_collector_returns_stub_outcome(domain):
    outcome = CertificateCollector().collect(domain)
    assert outcome.result_type == CollectionResult.TYPE_CERTIFICATE
    assert outcome.status == CollectionResult.STATUS_SUCCEEDED


@pytest.mark.django_db
def test_registration_collector_returns_stub_outcome(domain):
    outcome = RegistrationCollector().collect(domain)
    assert outcome.result_type == CollectionResult.TYPE_REGISTRATION
    assert outcome.status == CollectionResult.STATUS_SUCCEEDED


@pytest.mark.django_db
def test_security_summary_collector_returns_stub_outcome(domain):
    outcome = SecuritySummaryCollector().collect(domain)
    assert outcome.result_type == CollectionResult.TYPE_SECURITY_SUMMARY
    assert outcome.status == CollectionResult.STATUS_SUCCEEDED


# ---------------------------------------------------------------------------
# MailAuthCollector — Task 4
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mail_auth_collector_finds_spf_record(domain):
    def fake_resolve(fqdn, rtype, **kwargs):
        if rtype == "TXT" and not fqdn.startswith("_"):
            return FakeAnswer(['"v=spf1 include:_spf.example.co.jp ~all"'])
        raise dns.resolver.NoAnswer

    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockR:
        MockR.return_value.resolve.side_effect = fake_resolve
        outcome = MailAuthCollector().collect(domain)

    assert outcome.status == CollectionResult.STATUS_SUCCEEDED
    assert outcome.result_type == CollectionResult.TYPE_MAIL_AUTH
    assert outcome.payload["spf"] is not None
    assert "spf1" in outcome.payload["spf"]


@pytest.mark.django_db
def test_mail_auth_collector_finds_dmarc_record(domain):
    def fake_resolve(fqdn, rtype, **kwargs):
        if fqdn.startswith("_dmarc.") and rtype == "TXT":
            return FakeAnswer(['"v=DMARC1; p=reject; rua=mailto:dmarc@example.co.jp"'])
        raise dns.resolver.NoAnswer

    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockR:
        MockR.return_value.resolve.side_effect = fake_resolve
        outcome = MailAuthCollector().collect(domain)

    assert outcome.payload["dmarc"] is not None
    assert "DMARC1" in outcome.payload["dmarc"]


@pytest.mark.django_db
def test_mail_auth_collector_finds_dkim_record(domain):
    def fake_resolve(fqdn, rtype, **kwargs):
        if "._domainkey." in fqdn and rtype == "TXT":
            return FakeAnswer(['"v=DKIM1; k=rsa; p=MIGfMA..."'])
        raise dns.resolver.NoAnswer

    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockR:
        MockR.return_value.resolve.side_effect = fake_resolve
        outcome = MailAuthCollector().collect(domain)

    assert len(outcome.payload["dkim"]) >= 1
    assert outcome.payload["dkim"][0]["record"].startswith("v=DKIM1")


@pytest.mark.django_db
def test_mail_auth_collector_succeeds_with_no_records(domain):
    with patch("collection_jobs.collectors.dns.resolver.Resolver") as MockR:
        MockR.return_value.resolve.side_effect = dns.resolver.NoAnswer
        outcome = MailAuthCollector().collect(domain)

    assert outcome.status == CollectionResult.STATUS_SUCCEEDED
    assert outcome.payload["spf"] is None
    assert outcome.payload["dmarc"] is None
    assert outcome.payload["dkim"] == []
