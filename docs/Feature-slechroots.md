---
layout: default
title: Feature SUSE Linux Enterprise chroots
---
## Build packages for SUSE Linux Enterprise Server

Mock provides `sles-<RELEASEVER>-<TARGET_ARCH>` configs (for example `sles-15.7-x86_64` for SLES 15 SP7, or `sles-16.0-aarch64`) which build against the real SUSE Linux Enterprise Server repositories. You need a [SUSE subscription](https://www.suse.com/products/server/); a free 60-day evaluation is available at <https://www.suse.com/download/sles/>.

### How it works

SUSE does not publish static repository URLs for SUSE Linux Enterprise. At the start of every run, mock asks the registration server for the repositories of the product. That server is the SUSE Customer Center (SCC), or the RMT/SMT server set in `/etc/SUSEConnect`. SUSE's own [container-suseconnect](https://github.com/SUSE/container-suseconnect) does the same for containers.

* With SCC, every repository URL carries a short-lived CDN access token, so the URLs are fetched again on each run and are never stored in the config.
* With RMT/SMT, the repositories are protected by HTTP basic authentication. Mock writes the system credentials as `username`/`password` into the generated repositories in the chroot's `dnf.conf`.

The repositories of the base product are always added. Mock also adds the repositories of the extensions the server marks as recommended (for example the Basesystem, Server Applications and Python 3 modules on SLES 15; SLES 16 has no modules), plus the ones in `config_opts['suse_subscription_extensions']`. Debuginfo and source repositories are added but disabled, and you can turn them on with `--enablerepo`.

SUSE Linux Enterprise only ships `dnf` (SLES 15) and `dnf5` (SLES 16) in the SUSE Package Hub extension, and the SUSE container images only contain zypper. The host's package manager therefore installs the bootstrap chroot from the SLES repositories, with the Package Hub repositories added only there (`config_opts['suse_subscription_bootstrap_extensions']`). The buildroot is installed from the SLES repositories only, without Package Hub.

Package Hub packages are signed with the openSUSE Backports keys, which are only trusted for the Package Hub repositories (`config_opts['suse_subscription_bootstrap_gpgkey']`).

### Granting access

Mock can get access in one of three ways:

1. **Run mock on a registered SLES host.** Mock reads `/etc/zypp/credentials.d/SCCcredentials`, written by `SUSEConnect --regcode <REGISTRATION_CODE>`, and `/etc/SUSEConnect` if present.
2. **Copy the credentials of a registered system.** On a non-SUSE host, copy `/etc/zypp/credentials.d/SCCcredentials` (mode `0600`, owned by root) and optionally `/etc/SUSEConnect` from a registered system to the same paths. You can point at another credentials file with `config_opts['suse_subscription_credentials_file']`.
3. **Use a registration code** directly, for example in `~/.config/mock.cfg`:

   ```python
   config_opts['suse_subscription_regcode'] = '<REGISTRATION_CODE>'
   ```

   or on the command line:

   ```
   $ mock -r sles-15.7-x86_64 --config-opts=suse_subscription_regcode=<REGISTRATION_CODE> --shell
   ```

### Extensions and modules

Add extension identifiers to build with more of them:

```python
config_opts['suse_subscription_extensions'] += ['sle-module-desktop-applications', 'sle-module-web-scripting']
```

If you request an extension that doesn't exist for the product, mock fails and lists the extensions that are available. To use only the extensions you listed and none of the recommended ones, set `config_opts['suse_subscription_include_recommended'] = False`.

### Options

See `site-defaults.cfg` for all the `suse_subscription_*` options.
