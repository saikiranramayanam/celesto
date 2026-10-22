"""
Celesto Guest Network Policy Engine
Controls outbound connectivity from the microVM guest.
Used as defence-in-depth against prompt injection exfiltration attacks.
"""

from typing import List, Optional

class NetworkPolicy:
    def __init__(self, mode: str = "allow_list", allowed_hosts: Optional[List[str]] = None):
        self.mode = mode
        self.allowed_hosts = allowed_hosts or ["github.com", "pypi.org", "files.pythonhosted.org"]

    def is_egress_allowed(self, target_host: str) -> bool:
        if self.mode == "off":
            return False
        if self.mode == "allow_all":
            return True
        return target_host.lower() in self.allowed_hosts

    def evaluate_request(self, target_host: str) -> bool:
        allowed = self.is_egress_allowed(target_host)
        if not allowed:
            raise PermissionError(f"Network egress to '{target_host}' blocked by Celesto Network Policy.")
        return True
