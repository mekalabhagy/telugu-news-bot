"""Publish a card to Instagram via the official Graph API (Content Publishing).

Flow: upload JPEG to a public bucket -> create media container -> poll -> publish.
Requires an Instagram Business/Creator account linked to a Facebook Page.
"""
import mimetypes
import time
import uuid
from pathlib import Path

import requests

from config import (GRAPH_VERSION, IG_ACCESS_TOKEN, IG_USER_ID, S3_ACCESS_KEY,
                    S3_BUCKET, S3_ENDPOINT, S3_PUBLIC_BASE_URL, S3_SECRET_KEY)

BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def host_image(path: Path) -> str:
    """Upload to an S3-compatible bucket and return the public URL."""
    import boto3

    if not all([S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY, S3_PUBLIC_BASE_URL]):
        raise RuntimeError("S3_* settings are incomplete (see .env.example)")
    s3 = boto3.client(
        "s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY,
    )
    key = f"cards/{time.strftime('%Y%m%d')}/{uuid.uuid4().hex[:10]}{Path(path).suffix}"
    s3.upload_file(
        str(path), S3_BUCKET, key,
        ExtraArgs={"ContentType": mimetypes.guess_type(str(path))[0] or "image/jpeg"},
    )
    return f"{S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"


def _check(r: requests.Response):
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API {r.status_code}: {r.text[:400]}")
    return r.json()


def post_image(image_url: str, caption: str) -> str:
    if not (IG_USER_ID and IG_ACCESS_TOKEN):
        raise RuntimeError("IG_USER_ID / IG_ACCESS_TOKEN not set")
    created = _check(requests.post(
        f"{BASE}/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": IG_ACCESS_TOKEN},
        timeout=60,
    ))
    cid = created["id"]

    for _ in range(20):  # wait until Instagram has fetched and processed the image
        st = _check(requests.get(
            f"{BASE}/{cid}",
            params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
            timeout=30,
        )).get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container status {st}")
        time.sleep(3)
    else:
        raise RuntimeError("container not ready in time")

    pub = _check(requests.post(
        f"{BASE}/{IG_USER_ID}/media_publish",
        data={"creation_id": cid, "access_token": IG_ACCESS_TOKEN},
        timeout=60,
    ))
    return pub["id"]


def build_caption(card: dict, source_line: str) -> str:
    tags = " ".join(f"#{t}" for t in card.get("hashtags", []))
    parts = [card["caption_te"].strip(), f"మూలం: {source_line}", "AI సహాయంతో రూపొందించబడింది", tags]
    return "\n\n".join(p for p in parts if p)[:2200]
