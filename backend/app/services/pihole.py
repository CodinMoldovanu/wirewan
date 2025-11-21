import re
from typing import Optional

import httpx

from app.core.config import settings


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9-]", "-", name.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "service"


class PiHoleService:
    def __init__(self):
        self.api_url = settings.PIHOLE_API_URL
        self.token = settings.PIHOLE_API_TOKEN
        self.verify_ssl = settings.PIHOLE_VERIFY_SSL

    def is_configured(self) -> bool:
        return bool(self.api_url and self.token)

    def build_hostname(self, service_name: str, service_id: str, wan_name: Optional[str] = None) -> str:
        slug = _slugify(service_name)
        suffix = settings.DNS_SUFFIX or "lan"
        wan_part = _slugify(wan_name) if wan_name else None
        label_parts = [slug]
        if wan_part:
            label_parts.append(wan_part)
        label_parts.append(service_id[:6])
        return ".".join(label_parts + [suffix])

    async def add_record(self, hostname: str, ip: str) -> None:
        if not self.is_configured():
            return
        params = {
            "list": 1,
            "addhostname": hostname,
            "addip": ip,
            "token": self.token,
        }
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=10) as client:
            await client.post(self.api_url, params=params)

    async def delete_record(self, hostname: str, ip: str) -> None:
        if not self.is_configured():
            return
        params = {
            "list": 1,
            "delhostname": hostname,
            "ip": ip,
            "token": self.token,
        }
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=10) as client:
            await client.post(self.api_url, params=params)
