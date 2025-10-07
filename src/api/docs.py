# API version
VERSION = "0.1.0"

# Info for OpenAPI specification
TITLE = "InNoHassle Guard API"
SUMMARY = "Add users to Google Spreadsheets only after InNoHassle Accounts authentication."
DESCRIPTION = """
### About this project

This is the API for Guard project in InNoHassle ecosystem developed by [one-zero-eight](https://t.me/one_zero_eight) community.

Guard gates access to Google Spreadsheets by requiring users to authenticate via InNoHassle Accounts. Only authenticated users are added to spreadsheets with configured permissions (writer/reader). This ensures that only verified Innopolis University community members can access shared documents.

Backend is developed using FastAPI framework on Python.

Note: API is unstable. Endpoints and models may change in the future.

Useful links:
- [Guard API source code](https://github.com/one-zero-eight/guard)
- [InNoHassle Website](https://innohassle.ru)
"""

CONTACT_INFO = {
    "name": "one-zero-eight (Telegram)",
    "url": "https://t.me/one_zero_eight",
}

LICENSE_INFO = {
    "name": "MIT License",
    "identifier": "MIT",
}

TAGS_INFO = []
