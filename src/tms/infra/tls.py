"""TLS 1.2 or newer for every network connection (PRJ-SR-001).

``build_ssl_context`` returns a server context that refuses anything older than TLS 1.2.
``generate_self_signed`` makes a local certificate for the demo. ``scripts/run_https.py`` runs
the app with both.
"""
from __future__ import annotations

import datetime as dt
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

MINIMUM_VERSION = ssl.TLSVersion.TLSv1_2


def build_ssl_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = MINIMUM_VERSION
    context.load_cert_chain(certfile, keyfile)
    return context


def enforce_minimum_version(context: ssl.SSLContext) -> ssl.SSLContext:
    """Raise the floor of an existing context (used on the context uvicorn builds)."""
    context.minimum_version = MINIMUM_VERSION
    return context


def generate_self_signed(cert_path: str, key_path: str, common_name: str = "localhost", days: int = 365) -> None:
    """Write a self-signed certificate and key. For local demos only."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=1))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name), x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    Path(cert_path).parent.mkdir(parents=True, exist_ok=True)
    Path(cert_path).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    Path(key_path).write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    Path(key_path).chmod(0o600)
