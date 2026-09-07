config_opts['root'] = 'amazonlinux-2027-{{ target_arch }}'
config_opts['chroot_setup_cmd'] = 'install @buildsys-build'
#config_opts['chroot_setup_cmd'] = 'install bash bzip2 coreutils cpio diffutils file findutils gawk gcc gcc-c++ git glibc-all-langpacks glibc-locale-source grep gzip info kernel kernel-devel make patch python-rpm-macros python3-rpm-macros rpm-build rpmdevtools sed shadow-utils system-release system-rpm-config tar unzip util-linux wget which xz'
config_opts['dist'] = 'amzn2027' # only useful for --resultdir variable subst
config_opts['plugin_conf']['ccache_enable'] = False
config_opts['package_manager'] = 'dnf5'
config_opts['description'] = 'Amazon Linux 2027'
config_opts['releasever'] = '2027'

config_opts['bootstrap_image'] = 'public.ecr.aws/amazonlinux/amazonlinux:2027'

config_opts['dnf.conf'] = """
[main]
keepcache=1
debuglevel=2
reposdir=/dev/null
logfile=/var/log/yum.log
retries=20
obsoletes=1
gpgcheck=0
assumeyes=1
syslog_ident=mock
sysleg_device=
install_weak_deps=0
user_agent={{ user_agent }}

[amazonlinux]
name=Amazon Linux $releasever repository - $basearch
mirrorlist=https://al${releasever}-repos-us-west-2-7f9a3b4e.s3.dualstack.us-west-2.amazonaws.com/core/mirrors/latest/$basearch/mirror.list
enabled=1
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/amazon-linux/RPM-GPG-KEY-amazon-linux-$releasever

[amazonlinux-source]
name=Amazon Linux $releasever repository - Source packages
mirrorlist=https://al${releasever}-repos-us-west-2-7f9a3b4e.s3.dualstack.us-west-2.amazonaws.com/core/mirrors/latest/SRPMS/mirror.list
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/amazon-linux/RPM-GPG-KEY-amazon-linux-$releasever

[amazonlinux-debuginfo]
name=Amazon Linux $releasever repository - $basearch - Debug
mirrorlist=https://al${releasever}-repos-us-west-2-7f9a3b4e.s3.dualstack.us-west-2.amazonaws.com/core/mirrors/latest/debuginfo/$basearch/mirror.list
enabled=0
repo_gpgcheck=0
type=rpm
gpgcheck=1
gpgkey=file:///usr/share/distribution-gpg-keys/amazon-linux/RPM-GPG-KEY-amazon-linux-$releasever
"""
