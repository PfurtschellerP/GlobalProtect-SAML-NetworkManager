Name:           network-manager-gpclient
Version:        %{project_version}
Release:        1%{?dist}
Summary:        NetworkManager VPN plugin for GlobalProtect
License:        GPL-3.0-or-later
URL:            https://github.com/WMP/GlobalProtect-SAML-NetworkManager
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  cargo
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  cmake
BuildRequires:  extra-cmake-modules
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  git
BuildRequires:  glib2-devel
BuildRequires:  gtk3-devel
BuildRequires:  gtk4-devel
BuildRequires:  libnma-devel
BuildRequires:  libnma-gtk4-devel
BuildRequires:  NetworkManager-libnm-devel
BuildRequires:  openconnect-devel
BuildRequires:  openssl-devel
BuildRequires:  libxml2-devel
BuildRequires:  libtool
BuildRequires:  libsoup3-devel
BuildRequires:  javascriptcoregtk4.1-devel
BuildRequires:  webkit2gtk4.1-devel
BuildRequires:  plasma-nm
BuildRequires:  python3-devel
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qttools-devel
BuildRequires:  kf6-ki18n-devel
BuildRequires:  kf6-kservice-devel
BuildRequires:  kf6-kwidgetsaddons-devel
BuildRequires:  kf6-networkmanager-qt-devel

Requires:       NetworkManager
Requires:       openconnect
Requires:       python3
Conflicts:      globalprotect-openconnect

%description
NetworkManager VPN service and command-line tools for GlobalProtect VPN
connections with SAML/SSO authentication support.

%package gnome
Summary:        GNOME editor plugins for the GlobalProtect NetworkManager VPN
Requires:       %{name} = %{version}-%{release}
Requires:       NetworkManager-gnome
Requires:       libnma

%description gnome
GTK3 and GTK4 connection editor plugins for GlobalProtect VPN connections in
GNOME, MATE, Cinnamon, XFCE, and other GTK-based desktops.

%package plasma
Summary:        KDE Plasma 6 editor plugin for the GlobalProtect NetworkManager VPN
Requires:       %{name} = %{version}-%{release}
Requires:       plasma-nm
Conflicts:      %{name}-plasma5

%description plasma
KDE Plasma 6 NetworkManager connection editor plugin for GlobalProtect VPN
connections.

%prep
%autosetup -n %{name}-%{version}

%build
test -d external/GlobalProtect-openconnect/crates/openconnect/deps/openconnect
make -C plugins/gnome all
cd external/GlobalProtect-openconnect
cargo build --release --bin gpclient --bin gpauth --bin gpservice
cd -
cmake -S plugins/plasma -B build/plasma -DQT_MAJOR_VERSION=6 -DCMAKE_BUILD_TYPE=Release
cmake --build build/plasma

%install
install -D -m 0644 plugins/gnome/libnm-vpn-plugin-gpclient.so \
  %{buildroot}%{_libdir}/NetworkManager/libnm-vpn-plugin-gpclient.so
install -D -m 0644 plugins/gnome/libnm-vpn-plugin-gpclient-editor.so \
  %{buildroot}%{_libdir}/NetworkManager/libnm-vpn-plugin-gpclient-editor.so
install -D -m 0644 plugins/gnome/libnm-gtk4-vpn-plugin-gpclient-editor.so \
  %{buildroot}%{_libdir}/NetworkManager/libnm-gtk4-vpn-plugin-gpclient-editor.so
install -D -m 0644 plugins/gnome/nm-gpclient-service.name \
  %{buildroot}%{_prefix}/lib/NetworkManager/VPN/nm-gpclient-service.name
DESTDIR=%{buildroot} cmake --install build/plasma

install -D -m 0755 service/nm-gpclient-service.py \
  %{buildroot}%{_prefix}/lib/NetworkManager/nm-gpclient-service
install -D -m 0755 scripts/browser-wrapper.sh \
  %{buildroot}%{_libexecdir}/gpclient/browser-wrapper
install -D -m 0755 scripts/edge-wrapper.sh \
  %{buildroot}%{_libexecdir}/gpclient/edge-wrapper
install -D -m 0755 auth-dialog/nm-gpclient-auth-dialog.py \
  %{buildroot}%{_libexecdir}/nm-gpclient-auth-dialog
install -D -m 0755 external/GlobalProtect-openconnect/target/release/gpclient \
  %{buildroot}%{_bindir}/gpclient
install -D -m 0755 external/GlobalProtect-openconnect/target/release/gpauth \
  %{buildroot}%{_bindir}/gpauth
install -D -m 0755 external/GlobalProtect-openconnect/target/release/gpservice \
  %{buildroot}%{_bindir}/gpservice
install -D -m 0644 config/nm-gpclient.service \
  %{buildroot}%{_unitdir}/nm-gpclient.service
install -D -m 0644 config/org.freedesktop.NetworkManager.gpclient.service \
  %{buildroot}%{_datadir}/dbus-1/system-services/org.freedesktop.NetworkManager.gpclient.service
install -D -m 0644 config/nm-gpclient.conf \
  %{buildroot}%{_sysconfdir}/dbus-1/system.d/nm-gpclient.conf
install -D -m 0755 config/90-gpclient-routing \
  %{buildroot}%{_sysconfdir}/vpnc/connect.d/90-gpclient-routing
ln -s %{_libdir}/NetworkManager/libnm-vpn-plugin-gpclient-editor.so \
  %{buildroot}%{_prefix}/lib/libnm-gpclient-properties

%check
test -x %{buildroot}%{_bindir}/gpclient
test -f %{buildroot}%{_prefix}/lib/NetworkManager/VPN/nm-gpclient-service.name

%post
%systemd_post nm-gpclient.service

%preun
%systemd_preun nm-gpclient.service

%postun
%systemd_postun_with_restart nm-gpclient.service

%files
%license LICENSE
%doc README.md
%{_bindir}/gpclient
%{_bindir}/gpauth
%{_bindir}/gpservice
%{_libdir}/NetworkManager/libnm-vpn-plugin-gpclient.so
%{_prefix}/lib/NetworkManager/nm-gpclient-service
%{_prefix}/lib/NetworkManager/VPN/nm-gpclient-service.name
%{_libexecdir}/gpclient/browser-wrapper
%{_libexecdir}/gpclient/edge-wrapper
%{_unitdir}/nm-gpclient.service
%{_datadir}/dbus-1/system-services/org.freedesktop.NetworkManager.gpclient.service
%{_prefix}/lib/libnm-gpclient-properties
%config(noreplace) %{_sysconfdir}/dbus-1/system.d/nm-gpclient.conf
%config(noreplace) %{_sysconfdir}/vpnc/connect.d/90-gpclient-routing

%files gnome
%{_libdir}/NetworkManager/libnm-vpn-plugin-gpclient-editor.so
%{_libdir}/NetworkManager/libnm-gtk4-vpn-plugin-gpclient-editor.so
%{_libexecdir}/nm-gpclient-auth-dialog

%files plasma
%{_libdir}/qt6/plugins/plasma/network/vpn/plasmanetworkmanagement_gpclientui.so
%{_libdir}/qt6/plugins/plasma/network/vpn/plasmanetworkmanagement_gpclientui.json

%changelog
* Thu Jan 01 2026 WMP <wmp@users.noreply.github.com> - 1.5.0-1
- Add RPM packaging for Fedora and compatible distributions
