# RPM packages and repository

RPM packages are built for Fedora 44 on `x86_64` and `aarch64` in Fedora
containers. Each
release contains the following binary RPMs:

- `network-manager-gpclient`: the NetworkManager service and command-line tools
- `network-manager-gpclient-gnome`: GTK3/GTK4 connection editor plugins
- `network-manager-gpclient-plasma`: KDE Plasma 6 connection editor plugin

The packages are published at
<https://wmp.github.io/GlobalProtect-SAML-NetworkManager/rpm/>. Configure the
repository with:

```bash
python3 -m pip install --user sdbus

sudo rpm --import https://wmp.github.io/GlobalProtect-SAML-NetworkManager/rpm/gpclient-rpm-keyring.gpg
sudo tee /etc/yum.repos.d/gpclient.repo <<'EOF'
[gpclient]
name=GlobalProtect NetworkManager plugin
baseurl=https://wmp.github.io/GlobalProtect-SAML-NetworkManager/rpm
enabled=1
gpgcheck=0
repo_gpgcheck=1
gpgkey=https://wmp.github.io/GlobalProtect-SAML-NetworkManager/rpm/gpclient-rpm-keyring.gpg
EOF

sudo dnf install network-manager-gpclient-gnome
```

For KDE Plasma, install `network-manager-gpclient-plasma` instead.
