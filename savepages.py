#!/usr/bin/env python3

# Copyright (c) 2024 Pontus Lurcock

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import datetime
import json
import logging
import os
import time
from os import times
from typing import Optional

import click
import requests
import urllib3.util

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


HEADERS = dict(
    Authorization=(
        f"LOW {os.environ.get('IAACCESS')}:{os.environ.get('IASECRET')}"
    ),
    Accept="application/json",
)


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--delay", "-d", type=int, default=10)
@click.option("--no-outlinks-for", "-n", type=str, default=None)
@click.argument("url_list", type=str)
@click.argument("session_file", type=str, required=False, default=None)
def save(
    delay: int, no_outlinks_for: str, url_list: str, session_file: str
) -> None:
    retry_interval = 300

    for url in read_urls(url_list):
        outlinks = no_outlinks_for is None or no_outlinks_for not in url
        logger.info(f"Requesting save for {url} . outlinks={outlinks}")
        done = False
        while not done:
            response = make_save_request(url, outlinks)
            logger.info("Got response: " + response.text)
            jresp = response.json()
            if "job_id" in jresp:
                logger.info(f"Got job ID {jresp['job_id']} -- continuing.")
                if session_file:
                    with open(session_file, "a") as fh:
                        fh.write(response.text + "\n")
                done = True
                logger.info(f"Waiting {delay}s before next request.")
                time.sleep(delay)
            elif jresp.get("status") == "error":
                if jresp.get("status_ext") == "error:user-session-limit":
                    logger.warning("Session limit reached.")
                else:
                    logger.warning(f"Unknown error! {response.text}")
                logger.warning(f"waiting {retry_interval}s to retry.")
                time.sleep(retry_interval)


@cli.command()
@click.argument("session_file", type=str)
@click.argument("status_file", type=str)
def check(session_file: str, status_file: str):
    s = requests.Session()
    retries = urllib3.util.Retry(total=5, backoff_factor=10)
    s.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))
    with open(session_file, "r") as fh:
        records = [json.loads(line) for line in fh]
    for record in records:
        logger.info(f"Checking {record['url']}")
        if record["job_id"] is None:
            fh.write(str(record) + "\n")
        else:
            response = make_status_request(record["job_id"]).json()
            with open(status_file, "a") as fh:
                if response["status"] == "success":
                    fh.write("success " + response["original_url"] + "\n")
                else:
                    fh.write(response["status"] + " " + record["url"] + "\n")
            time.sleep(30)


@cli.command()
@click.argument("url-list", type=str)
def available(url_list: str):
    limit = datetime.timedelta(days=30)
    for url in read_urls(url_list):
        how_long_ago = parse_availability(make_availability_request(url).json())
        if how_long_ago is None:
            status = "!!!"
        elif how_long_ago > limit:
            status = "!  "
        else:
            status = "   "
        print(status, url, how_long_ago, flush=True)
        time.sleep(10)


def read_urls(url_list):
    with open(url_list, "r") as fh:
        urls = [line.rstrip() for line in fh]
    return urls


def make_save_request(url: str, outlinks: bool) -> requests.Response:
    return requests.post(
        "https://web.archive.org/save",
        data=dict(
            url=url,
            capture_outlinks={False: "0", True: "1"}[outlinks],
            skip_first_archive="1",
            if_not_archived_within="3d",
        ),
        headers=HEADERS,
    )


def make_status_request(job_id: str) -> requests.Response:
    return requests.post(
        "https://web.archive.org/save/status",
        data=dict(job_id=job_id),
        headers=HEADERS,
    )


def make_availability_request(url: str) -> requests.Response:
    return requests.get(
        "https://archive.org/wayback/available",
        params=dict(url=url),
        headers=dict(Accept="application/json"),
    )


def parse_availability(response: dict) -> Optional[datetime.timedelta]:
    timestamp = (
        response.get("archived_snapshots", {})
        .get("closest", {})
        .get("timestamp")
    )
    if timestamp is None:
        return None
    else:
        return datetime.datetime.now(
            tz=datetime.timezone.utc
        ) - datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(
            tzinfo=datetime.timezone.utc
        )


if __name__ == "__main__":
    cli()
