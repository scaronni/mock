# vim: noai:ts=4:sw=4:expandtab
"""Access to SUSE Linux Enterprise repositories through the SUSE Customer Center.

SUSE does not publish static repository URLs for SUSE Linux Enterprise.
The repositories a subscription grants access to are obtained from the
registration server (SCC, or a local RMT/SMT mirror), which returns the list
of repositories for a given product, version and architecture.  For SCC the
returned URLs carry a short-lived CDN access token in their query string, so
they are requested again on every mock run instead of being stored in the
configuration.

This mirrors what SUSE's own container-suseconnect does to give containers
access to the host's entitlements:

    https://github.com/SUSE/container-suseconnect

The result is stored in config_opts['suse_subscription_repos'] as a block of
dnf repository sections that the SLES templates include in their dnf.conf.
"""

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from . import exception

DEFAULT_SERVER = "https://scc.suse.com"
SUSECONNECT_CONFIG = "/etc/SUSEConnect"
REQUEST_TIMEOUT = 60


def _parse_key_value(text, separator):
    """Parse simple "key<separator>value" files like SCCcredentials or SUSEConnect.

    Args:
        text (str): The file content.
        separator (str): The character separating keys from values.

    Returns:
        dict: The parsed keys and values, both stripped of whitespace.
    """
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or separator not in line:
            continue
        key, value = line.split(separator, 1)
        result[key.strip()] = value.strip()
    return result


def _read_server(opts):
    """Return the registration server URL and whether to verify its TLS certificate."""
    server = opts["suse_subscription_server"]
    insecure = False
    if os.path.exists(SUSECONNECT_CONFIG):
        with open(SUSECONNECT_CONFIG, encoding="utf-8") as config_file:
            data = _parse_key_value(config_file.read(), ":")
        if not server:
            server = data.get("url")
        insecure = data.get("insecure", "false").lower() == "true"
    return (server or DEFAULT_SERVER).rstrip("/"), not insecure


def _read_credentials(opts, uid_manager):
    """Read the system credentials written by SUSEConnect when registering a system.

    The file is only readable by root, hence the elevated privileges.

    Returns:
        dict: The "username", "password" and optional "system_token" keys, or
        None if the credentials file does not exist.
    """
    path = opts["suse_subscription_credentials_file"]
    with uid_manager.elevated_privileges():
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as credentials_file:
            credentials = _parse_key_value(credentials_file.read(), "=")
    if not credentials.get("username") or not credentials.get("password"):
        raise exception.ConfigError(
            f"{path} does not contain a username and a password")
    return credentials


def _error_detail(response):
    """Extract a human readable error from a registration server response."""
    try:
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            return payload["error"]
    except ValueError:
        pass
    return f"HTTP {response.status_code} {response.reason}"


def _get(url, verify, auth=None, headers=None, params=None):
    try:
        return requests.get(url, auth=auth, headers=headers, params=params,
                            verify=verify, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as err:
        raise exception.ConfigError(
            f"Can not contact the SUSE registration server {url}: {err}")


def _system_auth(credentials):
    auth = (credentials["username"], credentials["password"])
    headers = {}
    if credentials.get("system_token"):
        headers["System-Token"] = credentials["system_token"]
    return auth, headers


def _request_regcodes(server, verify, credentials):
    """Ask the registration server for the registration codes of a registered system.

    Returns:
        list: The non-expired registration codes, or None if the server does
        not implement the endpoint, which is the case for RMT and SMT.
    """
    auth, headers = _system_auth(credentials)
    response = _get(server + "/connect/systems/subscriptions", verify,
                    auth=auth, headers=headers)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise exception.ConfigError(
            f"Can not retrieve the subscriptions of this system from {server}: {_error_detail(response)}")
    return [sub["regcode"] for sub in response.json()
            if sub.get("regcode") and str(sub.get("status", "")).upper() != "EXPIRED"]


def _parse_product(response):
    """Return the product from a products response, which can be an object or a list."""
    data = response.json()
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _request_product(server, verify, product_query, regcodes, credentials):
    """Retrieve the product tree, including all of its extensions and repositories.

    Args:
        server (str): Registration server URL.
        verify (bool): Whether to verify the server TLS certificate.
        product_query (dict): The "identifier", "version" and "arch" of the product.
        regcodes (list): Registration codes to try in order.  If None, the
            system credentials are used directly (RMT and SMT).
        credentials (dict): System credentials, only used if regcodes is None.

    Returns:
        dict: The product as returned by the registration server.
    """
    if regcodes is None:
        auth, headers = _system_auth(credentials)
        response = _get(server + "/connect/systems/products", verify,
                        auth=auth, headers=headers, params=product_query)
        if response.status_code == 200:
            return _parse_product(response)
        errors = [_error_detail(response)]
    else:
        errors = []
        for regcode in regcodes:
            response = _get(server + "/connect/subscriptions/products", verify,
                            headers={"Authorization": "Token token=" + regcode},
                            params=product_query)
            if response.status_code == 200:
                return _parse_product(response)
            errors.append(_error_detail(response))

    product_name = _product_name(product_query)
    reason = "; ".join(errors) or "no active subscription found"
    raise exception.ConfigError(f"No subscription gives access to {product_name}: {reason}")


def _product_name(product_query):
    return f"{product_query['identifier']} {product_query['version']} {product_query['arch']}"


def _walk_products(product):
    """Yield the product and, recursively, all of its extensions."""
    yield product
    for extension in product.get("extensions") or []:
        yield from _walk_products(extension)


def _select_repositories(product, extensions, include_recommended):
    """Return the repositories of the base product and of the selected extensions.

    Raises:
        ConfigError: If a requested extension does not exist for the product.
    """
    repositories = []
    seen_repos = set()
    seen_extensions = set()
    available = set()
    for index, item in enumerate(_walk_products(product)):
        identifier = item.get("identifier")
        if index:
            available.add(identifier)
            wanted = identifier in extensions or (include_recommended and item.get("recommended"))
            if not wanted:
                continue
            seen_extensions.add(identifier)
        for repo in item.get("repositories") or []:
            # The same module can appear as extension of several products.
            if repo["name"] in seen_repos:
                continue
            seen_repos.add(repo["name"])
            repositories.append(repo)

    missing = [ext for ext in extensions if ext not in seen_extensions]
    if missing:
        raise exception.ConfigError(
            f"Extension(s) {', '.join(missing)} not available for "
            f"{product.get('identifier')} {product.get('version')}.  "
            f"Available extensions: {', '.join(sorted(ext for ext in available if ext))}")
    return repositories


def _repository_auth(url, credentials):
    """Turn zypper's "?credentials=NAME" URL parameter into dnf basic authentication.

    RMT and SMT do not use CDN tokens but expect the system credentials to be
    sent with HTTP basic authentication; zypper does that when the URL carries a
    "credentials" query parameter.

    Returns:
        tuple: The URL without the "credentials" parameter and the
        (username, password) tuple to use, or None.
    """
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    filtered = [(key, value) for key, value in query if key != "credentials"]
    if credentials is None or len(filtered) == len(query):
        return url, None
    url = urlunsplit(parts._replace(query=urlencode(filtered)))
    return url, (credentials["username"], credentials["password"])


def _format_repositories(repositories, gpgkey, credentials):
    """Render the selected repositories as dnf.conf sections."""
    sections = []
    for repo in repositories:
        url, auth = _repository_auth(repo["url"], credentials)
        lines = [
            f"[{repo['name']}]",
            f"name={repo.get('description') or repo['name']}",
            f"baseurl={url}",
            f"enabled={1 if repo.get('enabled') else 0}",
            "sslverify=1",
            "skip_if_unavailable=False",
        ]
        if gpgkey:
            lines += ["gpgcheck=1", f"gpgkey={gpgkey}"]
        if auth:
            lines += [f"username={auth[0]}", f"password={auth[1]}"]
        sections.append("\n".join(lines) + "\n")
    return "\n".join(sections)


def subscription_suse_init(opts, uid_manager):
    """Fill config_opts['suse_subscription_repos'] for configs that need a SUSE subscription.

    Access is granted either by a registration code configured in
    config_opts['suse_subscription_regcode'], or by the system credentials of
    a host registered with SUSEConnect (SCC, RMT or SMT).

    Args:
        opts (dict): The mock configuration.
        uid_manager (UidManager): Used to read the root-only credentials file.

    Raises:
        ConfigError: If no subscription is available or the registration
            server does not return the requested product.
    """
    if not opts["suse_subscription_required"] or opts["suse_subscription_repos"]:
        return

    server, verify = _read_server(opts)
    product_query = {
        "identifier": opts["suse_subscription_product"],
        "version": opts["suse_subscription_version"],
        "arch": opts["suse_subscription_arch"],
    }

    credentials = None
    regcode = opts["suse_subscription_regcode"]
    if regcode:
        regcodes = [regcode]
    else:
        credentials = _read_credentials(opts, uid_manager)
        if credentials is None:
            credentials_file = opts["suse_subscription_credentials_file"]
            raise exception.ConfigError(
                f"This system is not registered with the SUSE Customer Center: {credentials_file} "
                "does not exist.  Either register it with\n"
                "  SUSEConnect --regcode <REGISTRATION_CODE>\n"
                f"copy {credentials_file} and {SUSECONNECT_CONFIG} from a registered system, or set\n"
                "  config_opts['suse_subscription_regcode'] = '<REGISTRATION_CODE>'\n"
                "You can get a free 60-day evaluation subscription at:\n"
                "  https://www.suse.com/download/sles/")
        regcodes = _request_regcodes(server, verify, credentials)
        if regcodes == []:
            raise exception.ConfigError(
                "The SUSE subscriptions of this system are all expired")

    product = _request_product(server, verify, product_query, regcodes, credentials)
    if not product:
        raise exception.ConfigError(f"{server} returned no product for {_product_name(product_query)}")

    # Basic authentication is only needed with RMT and SMT, which return no regcodes.
    repo_credentials = credentials if regcodes is None else None
    include_recommended = opts["suse_subscription_include_recommended"]
    extensions = opts["suse_subscription_extensions"]
    repositories = _select_repositories(product, extensions, include_recommended)
    opts["suse_subscription_repos"] = _format_repositories(
        repositories, opts["suse_subscription_gpgkey"], repo_credentials)

    bootstrap_extensions = opts["suse_subscription_bootstrap_extensions"]
    if bootstrap_extensions:
        # The bootstrap chroot gets additional repositories (e.g. Package Hub,
        # the only source of dnf), which must not leak into the buildroot.
        # Mock copies every 'bootstrap_<option>' over '<option>' in the
        # bootstrap config, so the same dnf.conf template picks these up.
        main_names = {repo["name"] for repo in repositories}
        extra = [repo for repo in _select_repositories(product, extensions + bootstrap_extensions,
                                                       include_recommended)
                 if repo["name"] not in main_names]
        extra_gpgkey = " ".join(key for key in (opts["suse_subscription_gpgkey"],
                                                opts["suse_subscription_bootstrap_gpgkey"]) if key)
        opts["bootstrap_suse_subscription_repos"] = "\n".join([
            opts["suse_subscription_repos"],
            _format_repositories(extra, extra_gpgkey, repo_credentials),
        ])
