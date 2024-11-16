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

import json
import logging
import os
import sys
import time

import click
import requests


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


HEADERS = dict(
    Authorization=(f"LOW {os.environ['IAACCESS']}:{os.environ['IASECRET']}"),
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

    with open(url_list, "r") as fh:
        urls = [line.rstrip() for line in fh]

    for url in urls:
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
                    logger.warn("Session limit reached.")
                else:
                    logger.warn(f"Unknown error! {response.text}")
                logger.warn(f"waiting {retry_interval}s to retry.")
                time.sleep(retry_interval)


@cli.command()
@click.argument("session_file", type=str)
def check(session_file: str):
    with open(session_file, "r") as fh:
        records = [json.loads(line) for line in fh]
    for record in records:
        response = make_status_request(record["job_id"]).json()
        print(response["status"] + " " + response["original_url"])


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


if __name__ == "__main__":
    cli()
