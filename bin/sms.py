#!/opt/splunk/bin/python3

import os
import sys
import re
import json
import configparser
import requests

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(APP_ROOT, "local", "sms.conf")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from splunklib.searchcommands import (
    StreamingCommand,
    Configuration,
    Option,
    dispatch,
)


@Configuration()
class SMSCommand(StreamingCommand):

    phone = Option(require=True)
    message = Option(require=True)
    mode = Option(require=False, default="first")
    dry_run = Option(require=False, default="false")

    def load_config(self):

        config = configparser.ConfigParser()

        if not os.path.exists(CONFIG_FILE):
            raise RuntimeError(
                "SMS configuration file not found: " + CONFIG_FILE
            )

        config.read(CONFIG_FILE)

        if not config.has_section("sms"):
            raise RuntimeError("Missing [sms] section in sms.conf")

        values = {
            "username": config.get("sms", "username", fallback=""),
            "password": config.get("sms", "password", fallback=""),
            "auth_url": config.get("sms", "auth_url", fallback=""),
            "sms_url": config.get("sms", "sms_url", fallback="")
        }

        for key, value in values.items():
            if not value:
                raise RuntimeError("SMS {} is missing".format(key))

        return values

    def authenticate(self, config):

        response = requests.post(
            config["auth_url"],
            json={
                "username": config["username"],
                "password": config["password"]
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        token = data.get("jwtToken")

        if not token:
            raise RuntimeError(
                "Authentication failed: jwtToken not found"
            )

        return token

    def send_sms(self, config, token, receiver, body):

        response = requests.post(
            config["sms_url"],
            headers={
                "Authorization": "Bearer {}".format(token),
                "Content-Type": "application/json"
            },
            json={
                "receiver": receiver,
                "body": body
            },
            timeout=10
        )

        response.raise_for_status()

        return response.text

    def render_message(self, template, record):

        def replace_field(match):

            field_name = match.group(1)

            value = record.get(field_name, "")

            if value is None:
                return ""

            return str(value)

        return re.sub(
            r"\{([A-Za-z_][A-Za-z0-9_]*)\}",
            replace_field,
            template
        )

    def stream(self, records):

        config = None
        token = None
        processed = False

        receivers = [
            number.strip()
            for number in str(self.phone).split(",")
            if number.strip()
        ]

        if not receivers:
            raise RuntimeError("No phone numbers were provided")

        mode = str(self.mode).lower()

        if mode not in ("first", "all"):
            raise RuntimeError(
                "mode must be either 'first' or 'all'"
            )

        dry_run = str(self.dry_run).lower() == "true"

        for record in records:

            if mode == "first" and processed:
                yield record
                continue

            processed = True

            try:

                body = self.render_message(
                    str(self.message),
                    record
                )

                record["sms_message"] = body

                if dry_run:

                    results = []

                    for receiver in receivers:
                        results.append({
                            "receiver": receiver,
                            "status": "simulation"
                        })

                    record["sms_status"] = "dry_run"
                    record["sms_results"] = json.dumps(
                        results,
                        ensure_ascii=False
                    )

                    yield record
                    continue

                if config is None:
                    config = self.load_config()

                if token is None:
                    token = self.authenticate(config)

                results = []

                for receiver in receivers:

                    try:

                        response = self.send_sms(
                            config,
                            token,
                            receiver,
                            body
                        )

                        results.append({
                            "receiver": receiver,
                            "status": "success",
                            "response": response
                        })

                    except Exception as exc:

                        results.append({
                            "receiver": receiver,
                            "status": "failed",
                            "error": str(exc)
                        })

                if all(
                    result["status"] == "success"
                    for result in results
                ):
                    record["sms_status"] = "success"
                else:
                    record["sms_status"] = "partial_or_failed"

                record["sms_results"] = json.dumps(
                    results,
                    ensure_ascii=False
                )

            except Exception as exc:

                record["sms_status"] = "failed"
                record["sms_results"] = json.dumps(
                    {
                        "error": str(exc)
                    },
                    ensure_ascii=False
                )

            yield record


dispatch(SMSCommand, sys.argv, sys.stdin, sys.stdout, __name__)
