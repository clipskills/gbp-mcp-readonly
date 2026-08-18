import pandas as pd
from googleapiclient.discovery import build

from src.gmb_mcp.logutil import get_logger

MYBUSINESS_V4_DISCOVERY_URL = "https://developers.google.com/my-business/samples/mybusiness_google_rest_v4p9.json"
POST_TOPIC_TYPES = {"STANDARD", "OFFER", "EVENT"}
POST_CTA_TYPES = {
    "BOOK",
    "ORDER",
    "SHOP",
    "LEARN_MORE",
    "SIGN_UP",
    "CALL",
}

logger = get_logger("data_fetcher")


def get_mybusiness_service(_credentials):
    """Returns a mybusiness v4 service client."""
    return build(
        "mybusiness",
        "v4",
        credentials=_credentials,
        discoveryServiceUrl=MYBUSINESS_V4_DISCOVERY_URL,
        static_discovery=False,
    )


def get_accounts(_credentials):
    """Fetches a list of accounts for the authenticated user."""
    try:
        service_account = build("mybusinessaccountmanagement", "v1", credentials=_credentials)
        accounts_result = service_account.accounts().list().execute()
        return accounts_result.get("accounts", [])
    except Exception as exc:
        logger.error("Error fetching accounts: %s", exc)
        return []


def get_account_for_location(_credentials, location_name):
    """Gets the account ID for a location by iterating through accounts.

    Args:
        _credentials: Google API credentials
        location_name: Location name in format 'locations/{locationId}'

    Returns:
        Full location path in format 'accounts/{accountId}/locations/{locationId}' or original name
    """
    try:
        if location_name.startswith("accounts/"):
            return location_name

        if not location_name.startswith("locations/"):
            return location_name

        location_id = location_name.replace("locations/", "")

        accounts = get_accounts(_credentials)
        service_business = build("mybusinessbusinessinformation", "v1", credentials=_credentials)

        for account in accounts:
            try:
                full_path = f"{account['name']}/locations/{location_id}"
                service_business.accounts().locations().get(
                    name=full_path,
                    readMask="name",
                ).execute()
                return full_path
            except Exception:
                continue

        return location_name
    except Exception:
        return location_name


def get_all_accessible_locations(_credentials):
    """Fetches ALL locations accessible by the user using v1 APIs.

    Iterates through all accounts and fetches locations from each.
    """
    try:
        accounts = get_accounts(_credentials)

        if not accounts:
            logger.warning("No accounts found.")
            return []

        all_locations = []
        service_business = build("mybusinessbusinessinformation", "v1", credentials=_credentials)
        read_mask = (
            "name,title,storefrontAddress,phoneNumbers,websiteUri,"
            "regularHours,categories,specialHours,serviceArea"
        )

        for account in accounts:
            try:
                page_token = None

                while True:
                    request_params = {
                        "parent": account["name"],
                        "readMask": read_mask,
                        "pageSize": 100,
                    }
                    if page_token:
                        request_params["pageToken"] = page_token

                    locations_result = service_business.accounts().locations().list(
                        **request_params
                    ).execute()
                    locations = locations_result.get("locations", [])

                    for loc in locations:
                        if not loc.get("name", "").startswith("accounts/"):
                            if loc.get("name", "").startswith("locations/"):
                                loc["name"] = f"{account['name']}/{loc['name']}"
                            else:
                                loc["name"] = f"{account['name']}/locations/{loc['name']}"

                    all_locations.extend(locations)

                    page_token = locations_result.get("nextPageToken")
                    if not page_token:
                        break

            except Exception:
                continue

        return all_locations

    except Exception as exc:
        logger.error("Error fetching locations: %s", exc)
        return []


def get_locations(_credentials, account_name=None):
    """Fetches locations for the specified account, or all locations if account_name is None."""
    if account_name is None:
        return get_all_accessible_locations(_credentials)

    try:
        service_business = build("mybusinessbusinessinformation", "v1", credentials=_credentials)
        read_mask = (
            "name,title,storefrontAddress,phoneNumbers,websiteUri,"
            "regularHours,categories,specialHours,serviceArea"
        )

        all_locations = []
        page_token = None

        while True:
            request_params = {
                "parent": account_name,
                "readMask": read_mask,
                "pageSize": 100,
            }
            if page_token:
                request_params["pageToken"] = page_token

            locations_result = service_business.accounts().locations().list(
                **request_params
            ).execute()
            locations = locations_result.get("locations", [])

            for loc in locations:
                if not loc.get("name", "").startswith("accounts/"):
                    if loc.get("name", "").startswith("locations/"):
                        loc["name"] = f"{account_name}/{loc['name']}"
                    else:
                        loc["name"] = f"{account_name}/locations/{loc['name']}"

            all_locations.extend(locations)

            page_token = locations_result.get("nextPageToken")
            if not page_token:
                break

        return all_locations
    except Exception as exc:
        logger.error("Error fetching locations from %s: %s", account_name, exc)
        return []


def extract_location_path(location_id):
    """Extracts the locations/{locationId} part from a full path.

    Args:
        location_id: Can be in format:
            - 'accounts/{accountId}/locations/{locationId}'
            - 'locations/{locationId}'
            - '{locationId}'

    Returns:
        'locations/{locationId}' format
    """
    if location_id.startswith("accounts/"):
        parts = location_id.split("/")
        if len(parts) >= 4 and parts[2] == "locations":
            return f"locations/{parts[3]}"

    if location_id.startswith("locations/"):
        return location_id

    return f"locations/{location_id}"


def resolve_location_parent(_credentials, location_id, account_name=None):
    """Resolves a location to accounts/{accountId}/locations/{locationId} format."""
    if location_id.startswith("accounts/"):
        return location_id

    if location_id.startswith("locations/"):
        if account_name:
            return f"{account_name}/{location_id}"
        full_location_path = get_account_for_location(_credentials, location_id)
        if full_location_path.startswith("accounts/"):
            return full_location_path
        raise ValueError(
            f"Could not find account for location '{location_id}'. Please provide account_name parameter."
        )

    if account_name:
        return f"{account_name}/locations/{location_id}"

    full_location_path = get_account_for_location(_credentials, f"locations/{location_id}")
    if full_location_path.startswith("accounts/"):
        return full_location_path
    raise ValueError(
        f"Could not find account for location '{location_id}'. Please provide account_name parameter."
    )


def build_local_post_payload(
    summary,
    topic_type="STANDARD",
    language_code="pt-BR",
    cta_type=None,
    cta_url=None,
    image_url=None,
):
    """Builds a validated local post payload for GBP API."""
    summary_clean = (summary or "").strip()
    if not summary_clean:
        raise ValueError("Summary is required.")

    topic_type_clean = (topic_type or "STANDARD").strip().upper()
    if topic_type_clean not in POST_TOPIC_TYPES:
        raise ValueError(f"Unsupported topic type: {topic_type_clean}")

    payload = {
        "languageCode": (language_code or "pt-BR").strip(),
        "summary": summary_clean,
        "topicType": topic_type_clean,
    }

    cta_type_clean = (cta_type or "").strip().upper()
    cta_url_clean = (cta_url or "").strip()
    if cta_type_clean or cta_url_clean:
        if cta_type_clean not in POST_CTA_TYPES:
            raise ValueError(
                "Invalid CTA type. Use one of: BOOK, ORDER, SHOP, LEARN_MORE, SIGN_UP, CALL."
            )
        if not (cta_url_clean.startswith("http://") or cta_url_clean.startswith("https://")):
            raise ValueError("CTA URL must start with http:// or https://")
        payload["callToAction"] = {"actionType": cta_type_clean, "url": cta_url_clean}

    image_url_clean = (image_url or "").strip()
    if image_url_clean:
        if not (image_url_clean.startswith("http://") or image_url_clean.startswith("https://")):
            raise ValueError("Image URL must start with http:// or https://")
        payload["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": image_url_clean}]

    return payload


def get_daily_metrics(_credentials, location_id, start_date, end_date):
    """Fetches daily metrics from API."""
    if not _credentials:
        logger.error("No credentials provided.")
        return pd.DataFrame()

    try:
        location_path = extract_location_path(location_id)

        service = build(
            "businessprofileperformance",
            "v1",
            credentials=_credentials,
            static_discovery=False,
        )

        metrics_to_fetch = [
            "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
            "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
            "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
            "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
            "WEBSITE_CLICKS",
            "CALL_CLICKS",
            "BUSINESS_DIRECTION_REQUESTS",
            "BUSINESS_CONVERSATIONS",
            "BUSINESS_BOOKINGS",
            "BUSINESS_FOOD_ORDERS",
        ]

        data = {}

        for metric in metrics_to_fetch:
            try:
                request = service.locations().getDailyMetricsTimeSeries(
                    name=location_path,
                    dailyMetric=metric,
                    dailyRange_startDate_year=start_date.year,
                    dailyRange_startDate_month=start_date.month,
                    dailyRange_startDate_day=start_date.day,
                    dailyRange_endDate_year=end_date.year,
                    dailyRange_endDate_month=end_date.month,
                    dailyRange_endDate_day=end_date.day,
                )
                response = request.execute()

                time_series = response.get("timeSeries")

                if time_series and isinstance(time_series, dict):
                    dated_values = time_series.get("datedValues", [])

                    for val in dated_values:
                        date_str = f"{val['date']['year']}-{val['date']['month']}-{val['date']['day']}"
                        date = pd.to_datetime(date_str)
                        value = int(val.get("value", 0))

                        if date not in data:
                            data[date] = {"date": date}

                        data[date][metric] = value

                elif time_series and isinstance(time_series, list):
                    for series in time_series:
                        dated_values = series.get("datedValues", [])
                        for val in dated_values:
                            date_str = (
                                f"{val['date']['year']}-{val['date']['month']}-{val['date']['day']}"
                            )
                            date = pd.to_datetime(date_str)
                            value = int(val.get("value", 0))

                            if date not in data:
                                data[date] = {"date": date}

                            data[date][metric] = value

            except Exception:
                pass

        final_data = list(data.values())
        if not final_data:
            logger.info("No metrics data found for this period.")
            return pd.DataFrame()

        df = pd.DataFrame(final_data).sort_values("date")

        for metric in metrics_to_fetch:
            if metric not in df.columns:
                df[metric] = 0

        return df.fillna(0)

    except Exception as exc:
        logger.error("Error fetching daily metrics: %s", exc)
        return pd.DataFrame()


def get_search_keywords(_credentials, location_id, start_date, end_date):
    """Fetches search keywords from API."""
    if not _credentials:
        return pd.DataFrame()

    try:
        location_path = extract_location_path(location_id)

        service = build(
            "businessprofileperformance",
            "v1",
            credentials=_credentials,
            static_discovery=False,
        )

        all_keywords = []
        next_page_token = None

        while True:
            request = service.locations().searchkeywords().impressions().monthly().list(
                parent=location_path,
                monthlyRange_startMonth_year=start_date.year,
                monthlyRange_startMonth_month=start_date.month,
                monthlyRange_endMonth_year=end_date.year,
                monthlyRange_endMonth_month=end_date.month,
                pageSize=100,
                pageToken=next_page_token,
            )
            response = request.execute()

            keywords_counts = response.get("searchKeywordsCounts", [])
            all_keywords.extend(keywords_counts)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        data = []
        for item in all_keywords:
            keyword = item.get("searchKeyword")
            insights_value = item.get("insightsValue", {})

            count = insights_value.get("value")
            threshold = insights_value.get("threshold")

            if count:
                data.append(
                    {
                        "keyword": keyword,
                        "count": int(count),
                        "display_count": str(count),
                    }
                )
            elif threshold:
                data.append(
                    {
                        "keyword": keyword,
                        "count": int(threshold),
                        "display_count": f"< {threshold}",
                    }
                )

        if not data:
            logger.info("No search keywords found for this period.")
            return pd.DataFrame(columns=["keyword", "count", "display_count"])

        return pd.DataFrame(data).sort_values("count", ascending=False)

    except Exception as exc:
        logger.error("Error fetching keywords: %s", exc)
        return pd.DataFrame()


def get_reviews(_credentials, location_id, account_name=None):
    """Fetches reviews for the specified location."""
    if not _credentials:
        return []

    try:
        service = get_mybusiness_service(_credentials)
        parent = resolve_location_parent(_credentials, location_id, account_name)

        reviews_result = service.accounts().locations().reviews().list(
            parent=parent,
            pageSize=50,
        ).execute()

        return reviews_result.get("reviews", [])
    except Exception as exc:
        logger.warning("Could not fetch reviews: %s", exc)
        return []


def reply_to_review(_credentials, review_name, comment, location_id=None, account_name=None):
    """Posts a reply to a GBP review via mybusiness v4 updateReply."""
    if not _credentials:
        raise ValueError("No credentials provided.")
    comment_clean = (comment or "").strip()
    if not comment_clean:
        raise ValueError("Reply comment is required.")

    name = (review_name or "").strip()
    if not name:
        raise ValueError("review_name is required.")

    if not name.startswith("accounts/"):
        if not location_id:
            raise ValueError(
                "review_name must be accounts/{accountId}/locations/{locationId}/reviews/{reviewId} "
                "or provide location_id so the parent path can be resolved."
            )
        parent = resolve_location_parent(_credentials, location_id, account_name)
        review_id = name.replace("reviews/", "")
        name = f"{parent}/reviews/{review_id}"

    service = get_mybusiness_service(_credentials)
    return service.accounts().locations().reviews().updateReply(
        name=name,
        body={"comment": comment_clean},
    ).execute()


def get_posts(_credentials, location_id, account_name=None):
    """Fetches local posts for the specified location."""
    if not _credentials:
        return []

    try:
        service = get_mybusiness_service(_credentials)
        parent = resolve_location_parent(_credentials, location_id, account_name)

        posts_result = service.accounts().locations().localPosts().list(
            parent=parent,
            pageSize=20,
        ).execute()

        return posts_result.get("localPosts", [])
    except Exception as exc:
        logger.warning("Could not fetch posts: %s", exc)
        return []


def create_local_post(_credentials, location_id, account_name=None, payload=None):
    """Creates a local post in Google Business Profile."""
    if not _credentials:
        raise ValueError("No credentials provided.")
    if not payload or not isinstance(payload, dict):
        raise ValueError("A valid post payload is required.")

    service = get_mybusiness_service(_credentials)
    parent = resolve_location_parent(_credentials, location_id, account_name)
    return service.accounts().locations().localPosts().create(
        parent=parent,
        body=payload,
    ).execute()


def get_media(_credentials, location_id, account_name=None):
    """Fetches media items for the specified location."""
    try:
        service_media = get_mybusiness_service(_credentials)
        parent = resolve_location_parent(_credentials, location_id, account_name)
        media_result = service_media.accounts().locations().media().list(
            parent=parent,
            pageSize=50,
        ).execute()
        return media_result.get("mediaItems", [])
    except Exception:
        return []


def get_location_details(_credentials, location_id, account_name=None):
    """Fetches a single location via mybusinessbusinessinformation v1."""
    if not _credentials:
        raise ValueError("No credentials provided.")

    read_mask = (
        "name,title,storefrontAddress,phoneNumbers,websiteUri,regularHours,"
        "categories,specialHours,serviceArea,openInfo,profile"
    )
    service = build("mybusinessbusinessinformation", "v1", credentials=_credentials)

    names_to_try = []
    try:
        names_to_try.append(resolve_location_parent(_credentials, location_id, account_name))
    except ValueError:
        pass
    location_only = extract_location_path(location_id)
    if location_only not in names_to_try:
        names_to_try.append(location_only)

    last_error = None
    for name in names_to_try:
        try:
            return service.accounts().locations().get(name=name, readMask=read_mask).execute()
        except Exception as exc:
            last_error = exc

    location_suffix = extract_location_path(location_id)
    for loc in get_locations(_credentials, account_name):
        loc_name = loc.get("name", "")
        if loc_name == location_id or loc_name.endswith(location_suffix):
            return loc

    if last_error:
        raise last_error
    raise ValueError(f"Location not found: {location_id}")


def get_questions(_credentials, location_id):
    """Fetches questions for the specified location."""
    try:
        location_path = extract_location_path(location_id)

        service_qa = build("mybusinessquestions", "v1", credentials=_credentials)
        questions_result = service_qa.locations().questions().list(
            parent=location_path,
            pageSize=20,
        ).execute()
        return questions_result.get("questions", [])
    except Exception:
        return []
