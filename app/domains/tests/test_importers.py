from domains.importers import ImportResult, parse_csv_file, parse_zone_file, parse_text_input


SAMPLE_ZONE = """\
$ORIGIN example.co.jp.
$TTL 3600
@       IN SOA  ns1.example.co.jp. admin.example.co.jp. (
                2026060501 3600 900 604800 300 )
@       IN NS   ns1.example.co.jp.
@       IN NS   ns2.example.co.jp.
@       IN A    203.0.113.1
api     IN A    203.0.113.2
api     IN AAAA 2001:db8::1
mail    IN MX   10 mail.example.co.jp.
dev     IN CNAME example.co.jp.
"""


def test_parse_zone_file_returns_import_results():
    results = parse_zone_file(SAMPLE_ZONE, origin="example.co.jp")
    assert isinstance(results, list)
    assert all(isinstance(result, ImportResult) for result in results)


def test_parse_zone_file_extracts_fqdns():
    results = parse_zone_file(SAMPLE_ZONE, origin="example.co.jp")
    fqdns = {result.fqdn for result in results if result.action != "error"}
    assert "example.co.jp" in fqdns
    assert "api.example.co.jp" in fqdns
    assert "dev.example.co.jp" in fqdns


def test_parse_zone_file_extracts_dns_records():
    results = parse_zone_file(SAMPLE_ZONE, origin="example.co.jp")
    a_records = [result for result in results if result.record_type == "A"]
    assert len(a_records) >= 2


def test_parse_zone_file_invalid_content_returns_error():
    results = parse_zone_file("INVALID ZONE CONTENT !!!", origin="example.co.jp")
    assert any(result.action == "error" for result in results)


SAMPLE_CSV = """\
fqdn,domain_type,status,mgmt_category,expires_at,purpose
example.co.jp,cctld,active,individual,2027-01-01,コーポレートドメイン
api.example.co.jp,subdomain,active,managed,,API サーバ
invalid..fqdn,gtld,active,managed,,bad fqdn
"""


def test_parse_csv_file_returns_import_results():
    results = parse_csv_file(SAMPLE_CSV)
    assert isinstance(results, list)
    assert all(isinstance(result, ImportResult) for result in results)


def test_parse_csv_file_valid_rows():
    results = parse_csv_file(SAMPLE_CSV)
    ok = [result for result in results if result.action == "create"]
    assert any(result.fqdn == "example.co.jp" for result in ok)
    assert any(result.fqdn == "api.example.co.jp" for result in ok)


def test_parse_csv_file_invalid_fqdn_marked_error():
    results = parse_csv_file(SAMPLE_CSV)
    errors = [result for result in results if result.action == "error"]
    assert any("invalid..fqdn" in result.fqdn for result in errors)


def test_parse_csv_file_maps_optional_fields():
    results = parse_csv_file(SAMPLE_CSV)
    corp = next(result for result in results if result.fqdn == "example.co.jp")
    assert corp.extra.get("purpose") == "コーポレートドメイン"
    assert corp.extra.get("expires_at") == "2027-01-01"


def test_parse_text_input_valid_fqdns():
    content = "example.co.jp\nsub.example.co.jp\n"
    results = parse_text_input(content)
    creates = [r for r in results if r.action == "create"]
    assert [r.fqdn for r in creates] == ["example.co.jp", "sub.example.co.jp"]


def test_parse_text_input_skips_blank_and_comment_lines():
    content = "example.co.jp\n\n# this is a comment\nsub.example.co.jp\n"
    results = parse_text_input(content)
    assert len(results) == 2
    assert all(r.action == "create" for r in results)


def test_parse_text_input_invalid_fqdn_marked_error():
    content = "valid.co.jp\n..invalid..\nother.co.jp\n"
    results = parse_text_input(content)
    errors = [r for r in results if r.action == "error"]
    assert len(errors) == 1
    assert errors[0].fqdn == "..invalid.."


def test_parse_text_input_empty_content_returns_empty_list():
    assert parse_text_input("") == []
    assert parse_text_input("# comment only\n") == []


def test_parse_text_input_normalizes_case():
    results = parse_text_input("Example.CO.JP\nSUB.Example.co.jp\n")
    fqdns = [r.fqdn for r in results if r.action == "create"]
    assert fqdns == ["example.co.jp", "sub.example.co.jp"]
