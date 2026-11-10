# Same set as the openSUSE patterns-devel-base-devel_rpm_build pattern, which
# does not exist in SUSE Linux Enterprise.
config_opts['chroot_setup_cmd'] = 'install man netcfg rpm-build sles-release'
config_opts['dist'] = 'sles15.7'  # only useful for --resultdir variable subst
config_opts['extra_chroot_dirs'] = [ '/run/lock', ]
config_opts['releasever'] = '15.7'
config_opts['package_manager'] = 'dnf'
config_opts['ssl_ca_bundle_path'] = '/var/lib/ca-certificates/ca-bundle.pem'
config_opts['description'] = 'SUSE Linux Enterprise Server 15 SP7'

# Repositories come from the SUSE Customer Center, see
# https://rpm-software-management.github.io/mock/Feature-slechroots
# rpm-build is in the Development Tools Module.
config_opts['suse_subscription_required'] = True
config_opts['suse_subscription_product'] = 'SLES'
config_opts['suse_subscription_version'] = '15.7'
config_opts['suse_subscription_extensions'] = [
    'sle-module-basesystem',
    'sle-module-server-applications',
    'sle-module-development-tools',
]
config_opts['suse_subscription_gpgkey'] = 'file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-SLE-15 file:///usr/share/distribution-gpg-keys/suse/RPM-GPG-KEY-SuSE-SLE-Main-2023'

# dnf is only shipped in SUSE Package Hub, whose packages are signed by the
# openSUSE Backports key.  Package Hub is only enabled in the bootstrap chroot,
# which is installed by the host's package manager (the SUSE container images
# only contain zypper), so the buildroot is made of SUSE supported packages only.
config_opts['use_bootstrap_image'] = False
config_opts['suse_subscription_bootstrap_extensions'] = ['PackageHub']
config_opts['suse_subscription_bootstrap_gpgkey'] = 'file:///usr/share/distribution-gpg-keys/opensuse/RPM-GPG-KEY-openSUSE-Backports-2023'

config_opts['dnf.conf'] = """
[main]
keepcache=1
debuglevel=2
reposdir=/dev/null
logfile=/var/log/yum.log
retries=20
obsoletes=1
gpgcheck=1
assumeyes=1
syslog_ident=mock
syslog_device=
install_weak_deps=0
metadata_expire=0
best=1

protected_packages=
user_agent={{ user_agent }}

# repos, generated from the SUSE Customer Center at every mock run

{{ suse_subscription_repos }}
"""
