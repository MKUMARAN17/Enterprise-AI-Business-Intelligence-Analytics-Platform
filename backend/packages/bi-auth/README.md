# bi-auth

Fail-closed JWT auth + table-level RBAC.

```python
from bi_auth import JwtValidator, RbacPolicy, Role, mint_dev_token

validator = JwtValidator(secret="dev-secret", audience="enterprise-bi", issuers=["enterprise-bi-dev"])
identity = validator.validate(token)            # -> Identity, or raises bi_base.AuthError
tables = RbacPolicy().allowed_tables(identity.role)   # allow-list handed to the SQL guard
```

- `Role` values mirror `ROLES.ROLE_NAME` (UPPERCASE): `BUSINESS_ANALYST`, `MANAGER`, `FINANCE`, `SALES`, `ADMIN`.
- HS256 (shared secret, dev) and RS256 (PEM public key, prod) share one validate path.
- RBAC is allow-list, table-level: `SALES` cannot read `CLAIMS`/`PAYMENTS`; only `ADMIN` reads platform tables.
