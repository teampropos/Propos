"""One-time discovery calls: list accounts and locations for a connected Google account."""

from .auth import ACCOUNT_MANAGEMENT_BASE_URL, BUSINESS_INFORMATION_BASE_URL

LOCATION_READ_MASK = "name,title"


def list_accounts(session) -> list[dict]:
    """List Google Business Profile accounts accessible to the connected account."""
    response = session.get(f"{ACCOUNT_MANAGEMENT_BASE_URL}/accounts")
    response.raise_for_status()
    return response.json().get("accounts", [])


def list_locations(session, account_name: str) -> list[dict]:
    """List locations under a given account.

    account_name is the full resource name, e.g. "accounts/1234567890".

    Each returned location dict has "name" as the bare "locations/{id}"
    form the Business Information API uses, plus a "review_path" field —
    the combined "accounts/{id}/locations/{id}" path the legacy reviews
    API (gbp.reviews) actually needs.
    """
    locations = []
    page_token = None

    while True:
        params = {"readMask": LOCATION_READ_MASK}
        if page_token:
            params["pageToken"] = page_token
        response = session.get(
            f"{BUSINESS_INFORMATION_BASE_URL}/{account_name}/locations",
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        for location in data.get("locations", []):
            location["review_path"] = f"{account_name}/{location['name']}"
            locations.append(location)
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return locations
