"""Mint a dev HS256 JWT for local testing.

    python scripts/mint_dev_token.py --role BUSINESS_ANALYST

Uses BI_JWT_SECRET from the environment (or --secret). The token is accepted by
the same JwtValidator the app runs, so you can call POST /api/v1/ask with it.
"""
from __future__ import annotations

import argparse
import os

from bi_auth import Role, mint_dev_token


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret", default=os.environ.get("BI_JWT_SECRET", "dev-secret"))
    ap.add_argument("--user-id", default="1")
    ap.add_argument("--username", default="analyst")
    ap.add_argument("--role", default="BUSINESS_ANALYST", choices=[r.value for r in Role])
    ap.add_argument("--audience", default=os.environ.get("BI_JWT_AUDIENCE", "enterprise-bi"))
    ap.add_argument("--issuer", default="enterprise-bi-dev")
    ap.add_argument("--ttl", type=int, default=3600)
    args = ap.parse_args()

    token = mint_dev_token(
        secret=args.secret,
        user_id=args.user_id,
        username=args.username,
        role=args.role,
        audience=args.audience,
        issuer=args.issuer,
        ttl_seconds=args.ttl,
    )
    print(token)


if __name__ == "__main__":
    main()
