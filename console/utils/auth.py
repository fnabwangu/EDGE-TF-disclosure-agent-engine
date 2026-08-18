def check_user(username: str) -> bool:
    # placeholder auth check
    return username == "admin"
"""## Authentication & Role-Based Access Control (`console/utils/auth.py`)

The `auth.py` module handles console session validation, role-based authorization (RBAC), and cryptographic credential verification for high-privilege operational tasks—including rebalance order release, portfolio disclosure transmission, and emergency kill-switch resets.

---

### Key Capabilities

* **`Role-Based Access Control (RBAC)`**: Grants specific granular permissions based on institutional fiduciary roles (`CHIEF_COMPLIANCE_OFFICER`, `LEAD_PORTFOLIO_MANAGER`, `CHIEF_FINANCIAL_OFFICER`, `OPERATIONS_TRADER`).
* **`Password / Token Hashing`**: Implements salted SHA-256 hashing for local credential authentication.
* **`Session Token Lifecycle`**: Issues expiring time-bound authorization tokens for terminal operators.
* **`Permission Verification Decorators`**: Provides decorators and verification guards to protect critical execution routines.
Python"""
# console/utils/auth.py
"""
EDGE-TF Disclosure Agent Engine - Console Authentication & RBAC Module.

Manages operator credentials, session authorization tokens, role hierarchy,
and permission enforcement for compliance and execution routines.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import hmac
import secrets
from typing import Callable, Dict, List, Optional, Set


class Role(str, Enum):
    CCO = "CHIEF_COMPLIANCE_OFFICER"
    LEAD_PM = "LEAD_PORTFOLIO_MANAGER"
    CFO = "CHIEF_FINANCIAL_OFFICER"
    OPERATIONS_TRADER = "OPERATIONS_TRADER"
    READ_ONLY_AUDITOR = "READ_ONLY_AUDITOR"


class Permission(str, Enum):
    VIEW_TELEMETRY = "VIEW_TELEMETRY"
    GENERATE_REBALANCE = "GENERATE_REBALANCE"
    SIGN_COMPLIANCE_TICKET = "SIGN_COMPLIANCE_TICKET"
    RELEASE_ORDERS_TO_BROKER = "RELEASE_ORDERS_TO_BROKER"
    PUBLISH_PCF_DISCLOSURE = "PUBLISH_PCF_DISCLOSURE"
    RESET_KILL_SWITCH = "RESET_KILL_SWITCH"
    EDIT_POLICY_CONFIG = "EDIT_POLICY_CONFIG"


# Default Role-to-Permission Matrix
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.CCO: {
        Permission.VIEW_TELEMETRY,
        Permission.SIGN_COMPLIANCE_TICKET,
        Permission.PUBLISH_PCF_DISCLOSURE,
        Permission.RESET_KILL_SWITCH,
        Permission.EDIT_POLICY_CONFIG,
    },
    Role.LEAD_PM: {
        Permission.VIEW_TELEMETRY,
        Permission.GENERATE_REBALANCE,
        Permission.SIGN_COMPLIANCE_TICKET,
        Permission.RELEASE_ORDERS_TO_BROKER,
        Permission.RESET_KILL_SWITCH,
    },
    Role.CFO: {
        Permission.VIEW_TELEMETRY,
        Permission.SIGN_COMPLIANCE_TICKET,
        Permission.EDIT_POLICY_CONFIG,
    },
    Role.OPERATIONS_TRADER: {
        Permission.VIEW_TELEMETRY,
        Permission.GENERATE_REBALANCE,
        Permission.RELEASE_ORDERS_TO_BROKER,
    },
    Role.READ_ONLY_AUDITOR: {
        Permission.VIEW_TELEMETRY,
    },
}


@dataclass
class UserSession:
    username: str
    role: Role
    token: str
    created_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at_utc: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=8)
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at_utc


class AuthManager:
    """
    Manages console user credentials, session tokens, and RBAC permission checks.
    """

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.active_sessions: Dict[str, UserSession] = {}
        # In-memory mock credential store: {username: {"salt": str, "hashed_pw": str, "role": Role}}
        self._user_db: Dict[str, Dict[str, Any]] = {}
        self._initialize_default_users()

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100_000
        ).hex()

    def register_user(self, username: str, password: str, role: Role):
        """Registers a user with a salted PBKDF2 SHA-256 password hash."""
        salt = secrets.token_hex(16)
        hashed_pw = self._hash_password(password, salt)
        self._user_db[username] = {
            "salt": salt,
            "hashed_pw": hashed_pw,
            "role": role
        }

    def _initialize_default_users(self):
        """Provisions bootstrap roles for testing and sandbox environments."""
        self.register_user("cco_admin", "CompliancePass2026!", Role.CCO)
        self.register_user("lead_pm", "AlphaManager2026!", Role.LEAD_PM)
        self.register_user("cfo_exec", "TreasuryPass2026!", Role.CFO)
        self.register_user("ops_desk", "ExecutionPass2026!", Role.OPERATIONS_TRADER)
        self.register_user("auditor", "AuditView2026!", Role.READ_ONLY_AUDITOR)

    def login(self, username: str, password: str) -> UserSession:
        """Authenticates user credentials and issues an expiring session token."""
        user_record = self._user_db.get(username)
        if not user_record:
            raise PermissionError("Invalid username or credentials.")

        expected_hash = user_record["hashed_pw"]
        computed_hash = self._hash_password(password, user_record["salt"])

        if not hmac.compare_digest(expected_hash, computed_hash):
            raise PermissionError("Invalid username or credentials.")

        session_token = secrets.token_urlsafe(32)
        session = UserSession(
            username=username,
            role=user_record["role"],
            token=session_token
        )
        self.active_sessions[session_token] = session
        return session

    def validate_session(self, token: str) -> UserSession:
        """Validates an active session token and checks for expiration."""
        session = self.active_sessions.get(token)
        if not session or session.is_expired:
            if session:
                del self.active_sessions[token]
            raise PermissionError("Session token is invalid or has expired.")
        return session

    def check_permission(self, token: str, required_permission: Permission) -> bool:
        """Verifies if the session role holds the required permission."""
        session = self.validate_session(token)
        user_permissions = ROLE_PERMISSIONS.get(session.role, set())
        return required_permission in user_permissions

    def require_permission(self, token: str, required_permission: Permission):
        """Raises PermissionError if the session lacks the designated permission."""
        if not self.check_permission(token, required_permission):
            session = self.validate_session(token)
            raise PermissionError(
                f"Access Denied: Role '{session.role.value}' does not have "
                f"permission '{required_permission.value}'."
            )

    def logout(self, token: str):
        """Terminates an active session."""
        if token in self.active_sessions:
            del self.active_sessions[token]


__all__ = [
    "Role",
    "Permission",
    "ROLE_PERMISSIONS",
    "UserSession",
    "AuthManager",
]
