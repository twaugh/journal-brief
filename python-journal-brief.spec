%global srcname journal-brief
%global sum Find new systemd journal entries since last run

Name:		python-%{srcname}
Version:	1.1.1
Release:	1%{?dist}
Summary:	%{sum}

License:	GPLv2+
URL:		https://pypi.python.org/pypi/%{srcname}
Source0:	https://pypi.python.org/packages/source/j/%{srcname}/%{srcname}-%{version}.tar.gz

BuildArch:	noarch
BuildRequires:	python3-devel
BuildRequires:	python3-pytest python3-flexmock
BuildRequires:	python3-PyYAML
Requires:	systemd-python3

%description
Python module for examining, bookmarking, and filtering systemd
journal entries.


%package -n %{srcname}
Summary:	Show interesting new systemd journal entries since last run
Requires:	python3-%{srcname} = %{version}-%{release}

%description -n %{srcname}
Run this from cron to get a daily or hourly briefing of interesting
new systemd journal entries.


%package -n python3-%{srcname}
Summary:	%{sum}
Recommends:	%{srcname} = %{version}-%{release}
%{?python_provide:%python_provide python3-%{srcname}}

%description -n python3-%{srcname}
Python module for examining, bookmarking, and filtering systemd
journal entries.


%prep
%autosetup -n %{srcname}-%{version}

%build
%py3_build


%install
%py3_install


%check
py.test-3.4 -v


%files -n %{srcname}
%{_bindir}/%{srcname}


%files -n python3-%{srcname}
%license LICENSE
%doc README.md
%{python3_sitelib}/*


%changelog
* Thu Oct 15 2015 Tim Waugh <twaugh@redhat.com> - 1.1.1-1
- Initial spec file.
