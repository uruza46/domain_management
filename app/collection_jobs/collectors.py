import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import dns.exception
import dns.resolver

from .models import CollectionResult

DNS_RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT"]
DNS_NAMESERVER = "8.8.8.8"
HTTP_TIMEOUT = 10  # seconds


@dataclass
class CollectionOutcome:
    result_type: str
    method: str
    source_name: str
    status: str
    payload: dict = field(default_factory=dict)
    raw_summary: str = ""
    error_code: str = ""
    error_message: str = ""
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Real collectors
# ---------------------------------------------------------------------------

class DnsRecordCollector:
    result_type = CollectionResult.TYPE_DNS_RECORDS

    def collect(self, domain) -> CollectionOutcome:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [DNS_NAMESERVER]
        records = []
        start = time.monotonic()

        for rtype in DNS_RECORD_TYPES:
            try:
                answers = resolver.resolve(domain.fqdn, rtype)
                for rdata in answers:
                    records.append({
                        "type": rtype,
                        "name": domain.fqdn,
                        "value": str(rdata),
                        "ttl": answers.ttl,
                    })
            except dns.resolver.NXDOMAIN:
                duration_ms = int((time.monotonic() - start) * 1000)
                return CollectionOutcome(
                    result_type=self.result_type,
                    method=CollectionResult.METHOD_DNS_QUERY,
                    source_name=DNS_NAMESERVER,
                    status=CollectionResult.STATUS_FAILED,
                    error_code="nxdomain",
                    error_message=f"{domain.fqdn} does not exist",
                    duration_ms=duration_ms,
                )
            except dns.exception.Timeout:
                duration_ms = int((time.monotonic() - start) * 1000)
                return CollectionOutcome(
                    result_type=self.result_type,
                    method=CollectionResult.METHOD_DNS_QUERY,
                    source_name=DNS_NAMESERVER,
                    status=CollectionResult.STATUS_FAILED,
                    error_code="timeout",
                    error_message="DNS query timed out",
                    duration_ms=duration_ms,
                )
            except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                pass

        duration_ms = int((time.monotonic() - start) * 1000)
        return CollectionOutcome(
            result_type=self.result_type,
            method=CollectionResult.METHOD_DNS_QUERY,
            source_name=DNS_NAMESERVER,
            status=CollectionResult.STATUS_SUCCEEDED,
            payload={"records": records},
            raw_summary=f"{len(records)} record(s)",
            duration_ms=duration_ms,
        )


class HttpStatusCollector:
    result_type = CollectionResult.TYPE_HTTP_STATUS

    def collect(self, domain) -> CollectionOutcome:
        url = f"https://{domain.fqdn}"
        start = time.monotonic()
        redirects = []

        class _RedirectRecorder(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                redirects.append(req.full_url)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        opener = urllib.request.build_opener(_RedirectRecorder)
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "DomainManagement/1.0")

        try:
            with opener.open(req, timeout=HTTP_TIMEOUT) as response:
                duration_ms = int((time.monotonic() - start) * 1000)
                return CollectionOutcome(
                    result_type=self.result_type,
                    method=CollectionResult.METHOD_HTTP_HEAD,
                    source_name=url,
                    status=CollectionResult.STATUS_SUCCEEDED,
                    payload={
                        "status_code": response.status,
                        "final_url": response.url,
                        "redirects": redirects,
                        "duration_ms": duration_ms,
                    },
                    raw_summary=f"HTTP {response.status}",
                    duration_ms=duration_ms,
                )
        except socket.timeout:
            duration_ms = int((time.monotonic() - start) * 1000)
            return CollectionOutcome(
                result_type=self.result_type,
                method=CollectionResult.METHOD_HTTP_HEAD,
                source_name=url,
                status=CollectionResult.STATUS_FAILED,
                error_code="timeout",
                error_message="HTTP request timed out",
                duration_ms=duration_ms,
            )
        except urllib.error.URLError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            reason = getattr(exc, "reason", None)
            if isinstance(reason, (socket.timeout, TimeoutError)):
                error_code, error_message = "timeout", "HTTP request timed out"
            else:
                error_code, error_message = "connection_error", str(exc)[:200]
            return CollectionOutcome(
                result_type=self.result_type,
                method=CollectionResult.METHOD_HTTP_HEAD,
                source_name=url,
                status=CollectionResult.STATUS_FAILED,
                error_code=error_code,
                error_message=error_message,
                duration_ms=duration_ms,
            )


# ---------------------------------------------------------------------------
# Stub collectors (real implementation deferred)
# ---------------------------------------------------------------------------

class MailAuthCollector:
    result_type = CollectionResult.TYPE_MAIL_AUTH
    DKIM_SELECTORS = ["google", "default", "selector1", "selector2", "mail"]

    def collect(self, domain) -> CollectionOutcome:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [DNS_NAMESERVER]
        start = time.monotonic()

        spf = self._find_spf(resolver, domain.fqdn)
        dmarc = self._find_dmarc(resolver, domain.fqdn)
        dkim = self._find_dkim(resolver, domain.fqdn)

        duration_ms = int((time.monotonic() - start) * 1000)
        parts = (
            (["SPF"] if spf else [])
            + (["DMARC"] if dmarc else [])
            + ([f"DKIM({len(dkim)})"] if dkim else [])
        )
        return CollectionOutcome(
            result_type=self.result_type,
            method=CollectionResult.METHOD_DNS_QUERY,
            source_name=DNS_NAMESERVER,
            status=CollectionResult.STATUS_SUCCEEDED,
            payload={"spf": spf, "dmarc": dmarc, "dkim": dkim},
            raw_summary=", ".join(parts) if parts else "no mail auth records found",
            duration_ms=duration_ms,
        )

    def _find_spf(self, resolver, fqdn):
        try:
            for rdata in resolver.resolve(fqdn, "TXT"):
                txt = str(rdata).strip('"')
                if txt.startswith("v=spf1"):
                    return txt
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                dns.resolver.NoNameservers, dns.exception.Timeout):
            pass
        return None

    def _find_dmarc(self, resolver, fqdn):
        try:
            for rdata in resolver.resolve(f"_dmarc.{fqdn}", "TXT"):
                txt = str(rdata).strip('"')
                if txt.startswith("v=DMARC1"):
                    return txt
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                dns.resolver.NoNameservers, dns.exception.Timeout):
            pass
        return None

    def _find_dkim(self, resolver, fqdn):
        results = []
        for selector in self.DKIM_SELECTORS:
            try:
                for rdata in resolver.resolve(f"{selector}._domainkey.{fqdn}", "TXT"):
                    txt = str(rdata).strip('"')
                    if "v=DKIM1" in txt:
                        results.append({"selector": selector, "record": txt})
                        break
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                    dns.resolver.NoNameservers, dns.exception.Timeout):
                pass
        return results


class CertificateCollector:
    result_type = CollectionResult.TYPE_CERTIFICATE

    def collect(self, domain) -> CollectionOutcome:
        return CollectionOutcome(
            result_type=self.result_type,
            method=CollectionResult.METHOD_CT_LOG,
            source_name="stub",
            status=CollectionResult.STATUS_SUCCEEDED,
            payload={},
            raw_summary="[stub] certificate collection not yet implemented",
        )


class RegistrationCollector:
    result_type = CollectionResult.TYPE_REGISTRATION

    def collect(self, domain) -> CollectionOutcome:
        return CollectionOutcome(
            result_type=self.result_type,
            method=CollectionResult.METHOD_RDAP,
            source_name="stub",
            status=CollectionResult.STATUS_SUCCEEDED,
            payload={},
            raw_summary="[stub] registration collection not yet implemented",
        )


class SecuritySummaryCollector:
    result_type = CollectionResult.TYPE_SECURITY_SUMMARY

    def collect(self, domain) -> CollectionOutcome:
        return CollectionOutcome(
            result_type=self.result_type,
            method=CollectionResult.METHOD_DERIVED,
            source_name="stub",
            status=CollectionResult.STATUS_SUCCEEDED,
            payload={},
            raw_summary="[stub] security summary not yet implemented",
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

COLLECTORS = {
    CollectionResult.TYPE_DNS_RECORDS: DnsRecordCollector(),
    CollectionResult.TYPE_HTTP_STATUS: HttpStatusCollector(),
    CollectionResult.TYPE_MAIL_AUTH: MailAuthCollector(),
    CollectionResult.TYPE_CERTIFICATE: CertificateCollector(),
    CollectionResult.TYPE_REGISTRATION: RegistrationCollector(),
    CollectionResult.TYPE_SECURITY_SUMMARY: SecuritySummaryCollector(),
}
