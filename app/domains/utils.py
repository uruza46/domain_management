def reverse_fqdn(fqdn: str) -> str:
    """Return FQDN labels in reversed order for namespace sorting.

    'api.dev.example.co.jp' -> 'jp.co.example.dev.api'
    """
    return ".".join(reversed(fqdn.rstrip(".").split(".")))
