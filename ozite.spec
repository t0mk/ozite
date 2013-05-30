Summary: Tool for image creation and glance upload
Name: ozite
Version: 0.4
Release: 1%{?dist}

License: GPL
Group: System Environment/Base
URL: http://www.cern.ch/ai
Source: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

Requires: oz,qemu-img,python-glance,python-argparse

%description
Ozite is a tool for creating images from templates and uploading then to
Openstack. It makes use of Aeolus Oz and Python API for Openstack Glance.

%prep
%setup -q

%build
CFLAGS="%{optflags}" %{__python} setup.py build

%install
%{__rm} -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot}
mkdir -p %{buildroot}/usr/bin
install -m 755 build/lib/ozite/ozite.py %{buildroot}/usr/bin/ozite

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{python_sitelib}/*
/usr/bin/ozite

%changelog
* Thu May 30 2013 Jan van Eldik <Jan.van.Eldik@cern.ch> - 0.4-1
- [bug] remove unsupported compression option for vpc images

* Fri May 24 2013 Jan van Eldik <Jan.van.Eldik@cern.ch> - 0.3-2
- Properly install /usr/bin/ozite

* Fri May 24 2013 Jan van Eldik <Jan.van.Eldik@cern.ch> - 0.3-1
- Remove dependency on VirtualBox

* Mon Apr 22 2013 Tomas Karasek <tomas.karasek@cern.ch> - 0.2-1
- fixed post-install and OS_CACERT x OS_CA_CERT problem

* Mon Mar 18 2013 Tomas Karasek <tomas.karasek@cern.ch> - 0.1-2
- fixed deps and added raw image format for faster debugging of images

* Fri Feb 08 2013 Tomas Karasek <tomas.karasek@cern.ch> - 0.1-1
- First release
