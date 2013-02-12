Summary: Tool for image creation and glance upload
Name: ozite
Version: 0.1
Release: 1%{?dist}

License: GPL
Group: System Environment/Base
URL: http://www.cern.ch/ai
Source: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

Requires: oz,qemu-img,VirtualBox-4.2,python-glance,python-argparse

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

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{python_sitelib}/*

%post
ln -s %{python_sitelib}/ozite/ozite.py /usr/bin/ozite
chmod +x %{python_sitelib}/ozite/ozite.py 

%preun
rm /usr/bin/ozite


%changelog
* Fri Feb 08 2013 Tomas Karasek <tomas.karasek@cern.ch> - 0.1-1
- First release
