import base64
import subprocess
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class WireGuardKeyPair:
    private_key: str
    public_key: str


class WireGuardService:
    """Service for WireGuard key management and operations."""

    @staticmethod
    def generate_keypair() -> WireGuardKeyPair:
        """Generate a new WireGuard keypair."""
        # Try using the wg command if available
        try:
            private_key = subprocess.check_output(
                ["wg", "genkey"],
                stderr=subprocess.DEVNULL
            ).decode().strip()

            public_key = subprocess.check_output(
                ["wg", "pubkey"],
                input=private_key.encode(),
                stderr=subprocess.DEVNULL
            ).decode().strip()

            return WireGuardKeyPair(private_key=private_key, public_key=public_key)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fall back to Python implementation using cryptography
            return WireGuardService._generate_keypair_python()

    @staticmethod
    def _generate_keypair_python() -> WireGuardKeyPair:
        """Generate keypair using Python cryptography library."""
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives import serialization

        private_key = X25519PrivateKey.generate()

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_key_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        return WireGuardKeyPair(
            private_key=base64.b64encode(private_key_bytes).decode(),
            public_key=base64.b64encode(public_key_bytes).decode()
        )

    @staticmethod
    def derive_public_key(private_key: str) -> Optional[str]:
        """Derive public key from private key."""
        try:
            public_key = subprocess.check_output(
                ["wg", "pubkey"],
                input=private_key.encode(),
                stderr=subprocess.DEVNULL
            ).decode().strip()
            return public_key
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fall back to Python implementation
            return WireGuardService._derive_public_key_python(private_key)

    @staticmethod
    def _derive_public_key_python(private_key: str) -> Optional[str]:
        """Derive public key using Python cryptography library."""
        try:
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            from cryptography.hazmat.primitives import serialization

            private_key_bytes = base64.b64decode(private_key)
            private_key_obj = X25519PrivateKey.from_private_bytes(private_key_bytes)

            public_key_bytes = private_key_obj.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            return base64.b64encode(public_key_bytes).decode()
        except Exception:
            return None

    @staticmethod
    def validate_public_key(key: str) -> bool:
        """Validate a WireGuard public key format."""
        try:
            decoded = base64.b64decode(key)
            return len(decoded) == 32
        except Exception:
            return False

    @staticmethod
    def validate_private_key(key: str) -> bool:
        """Validate a WireGuard private key format."""
        try:
            decoded = base64.b64decode(key)
            return len(decoded) == 32
        except Exception:
            return False

    @staticmethod
    def generate_preshared_key() -> str:
        """Generate a pre-shared key."""
        try:
            psk = subprocess.check_output(
                ["wg", "genpsk"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            return psk
        except (subprocess.CalledProcessError, FileNotFoundError):
            import secrets
            return base64.b64encode(secrets.token_bytes(32)).decode()
