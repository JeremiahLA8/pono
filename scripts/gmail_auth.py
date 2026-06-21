#!/usr/bin/env python3
"""
One-time Gmail OAuth setup for Jeremiah's AIOS.

Run this once per Gmail account you want to connect. It opens your browser,
you approve READ-ONLY access, and it saves a reusable token so you never have
to log in again (until you revoke it).

Usage:
    # Primary account (default token file):
    scripts/.venv/bin/python scripts/gmail_auth.py

    # A second account, saved to its own token file:
    scripts/.venv/bin/python scripts/gmail_auth.py --token token_secondary.json

Requires scripts/credentials.json (the OAuth client you download from Google
Cloud Console). See references/gmail-api.md for the setup walkthrough.
"""
import argparse
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# READ-ONLY. This token can never send, delete, or modify mail.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description="Authorize a Gmail account (read-only).")
    parser.add_argument(
        "--credentials",
        default=os.path.join(HERE, "credentials.json"),
        help="Path to the OAuth client file downloaded from Google Cloud Console.",
    )
    parser.add_argument(
        "--token",
        default="token.json",
        help="Filename to save the authorized token (relative to scripts/). "
        "Use a different name per account, e.g. token_secondary.json.",
    )
    args = parser.parse_args()

    token_path = os.path.join(HERE, args.token)

    if not os.path.exists(args.credentials):
        sys.exit(
            f"\nMissing OAuth client file: {args.credentials}\n"
            "Download it from Google Cloud Console (see references/gmail-api.md) "
            "and save it as scripts/credentials.json.\n"
        )

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if creds and creds.valid:
        print(f"Already authorized. Token is valid: {token_path}")
        return

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        print("Refreshed an expired token.")
    else:
        flow = InstalledAppFlow.from_client_secrets_file(args.credentials, SCOPES)
        # Opens your browser; you approve on Google's own screen.
        creds = flow.run_local_server(port=0, prompt="consent")
        print("Authorized successfully.")

    with open(token_path, "w") as f:
        f.write(creds.to_json())
    os.chmod(token_path, 0o600)  # owner-only read/write
    print(f"Saved token to {token_path} (this file is gitignored — keep it private).")


if __name__ == "__main__":
    main()
