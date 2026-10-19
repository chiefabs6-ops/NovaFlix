"""Shared test helpers: fixture loading and a scripted fake network."""

import json
import os

from resources.lib.net import http

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


class Replies:
    """Answers for one route used in order; the last one repeats. Each answer is (status, body)."""

    def __init__(self, *answers):
        self.answers = list(answers)

    def next(self):
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


class FakeNet:
    """Answers requests by matching URL substrings (and optional body text).

    route("graphql.anilist.co", data, body_contains="TRENDING_DESC")
    A value that is an exception instance is raised instead.
    """

    def __init__(self):
        self.routes = []
        self.calls = []
        self.headers = []
        http.set_transport(self)

    def route(self, url_part, response, body_contains=None, status=200):
        self.routes.append((url_part, body_contains, response, status))
        return self

    def __call__(self, method, url, headers, body, timeout, context):
        text = body.decode("utf-8") if body else ""
        self.calls.append((method, url, text))
        self.headers.append(dict(headers))
        for url_part, body_contains, response, status in self.routes:
            if url_part in url and (body_contains is None or body_contains in text):
                if isinstance(response, Replies):
                    status, response = response.next()
                if isinstance(response, BaseException):
                    raise response
                return status, {}, json.dumps(response).encode("utf-8")
        raise AssertionError(f"unexpected request {method} {url} {text[:120]}")

    def count(self, url_part):
        return sum(1 for _, url, _ in self.calls if url_part in url)


MAL_CLIENT = "TESTMALCLIENTID000000000000000001"
MAL_ACCESS = "ACCESSTOKENMAL0000000000000000001"
MAL_REFRESH = "REFRESHTOKENMAL000000000000000001"
MAL_TOKEN = {"token_type": "Bearer", "expires_in": 2678400, "access_token": MAL_ACCESS, "refresh_token": MAL_REFRESH}


def mal_login(expires_at=4_000_000_000.0, username="owner"):
    """Store a MyAnimeList login in the test profile (valid far into the future unless told otherwise)."""
    from resources.lib.kodi import paths
    from resources.lib.myanimelist import auth
    store = auth.MalStore(paths.profile_dir())
    store.save(client_id=MAL_CLIENT, username=username, access_token=MAL_ACCESS,
               refresh_token=MAL_REFRESH, expires_at=expires_at)
    return store
