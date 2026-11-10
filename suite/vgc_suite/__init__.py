

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

__version__ = "0.2.0"
