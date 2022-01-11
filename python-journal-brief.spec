%global srcname journal-brief
%global sum Find new systemd journal entries since last run

Name:		python-%{srcname}
Version:	1.1.8
Release:	1%{?dist}
Summary:	%{sum}

License:	GPLv2+
URL:		https://pypi.python.org/pypi/%{srcname}
Source0:	https://pypi.python.org/packages/source/j/%{srcname}/%{srcname}-%{version}.tar.gz

BuildArch:	noarch
BuildRequires:	python3-devel
BuildRequires:	python3-pytest python3-flexmock python3-pytest-mock
BuildRequires:	python3-PyYAML
BuildRequires:	python3-setuptools

%description
Python module for examining, bookmarking, and filtering systemd
journal entries.


%package -n %{srcname}
Summary:	Show interesting new systemd journal entries since last run
Requires:	python3-%{srcname} = %{version}-%{release}
Requires:	python3-setuptools

%description -n %{srcname}
Run this from cron to get a daily or hourly briefing of interesting
new systemd journal entries.


%package -n python3-%{srcname}
Summary:	%{sum}
Requires:	systemd-python3
Requires:	python3-PyYAML
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
PYTEST_ARGS='-v --doctest-modules tests journal_brief'
%{__python3} %{py_setup} test --pytest-args="$PYTEST_ARGS"


%files -n %{srcname}
%{_bindir}/%{srcname}


%files -n python3-%{srcname}
%license LICENSE
%doc README.md
%{python3_sitelib}/*


%changelog
* Tue Jan 11 2022 Tim Waugh <twaugh@redhat.com> - 1.1.8-1
- 1.1.8.

* Mon Jul 13 2020 Tim Waugh <twaugh@redhat.com> - 1.1.7-1
- 1.1.7.

* Tue Jul  7 2020 Tim Waugh <twaugh@redhat.com> - 1.1.6-1
- 1.1.6.

* Mon Oct 31 2016 Tim Waugh <twaugh@redhat.com> - 1.1.5-1
- 1.1.5.

* Sun Jul 24 2016 Tim Waugh <twaugh@redhat.com> - 1.1.4-1
- 1.1.4.

* Mon Nov  9 2015 Tim Waugh <twaugh@redhat.com> - 1.1.3-1
- 1.1.3.

* Fri Oct 30 2015 Tim Waugh <twaugh@redhat.com> - 1.1.2-1
- 1.1.2.

* Thu Oct 15 2015 Tim Waugh <twaugh@redhat.com> - 1.1.1-1
- Initial spec file.
