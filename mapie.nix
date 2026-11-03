{
  lib,
  buildPythonPackage,
  fetchPypi,
  numpy,
  scikit-learn,
  scipy,
  setuptools,
  setuptools-scm,
}:

buildPythonPackage rec {
  pname = "mapie";
  version = "1.5.0";
  pyproject = true;

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-G2qBeX1UmwMz1vaGW9O8pNJsQQN/ER/YQWDqh6cMbXI=";
  };

  build-system = [
    setuptools
    setuptools-scm
  ];

  dependencies = [
    numpy
    scikit-learn
    scipy
  ];

  env.SETUPTOOLS_SCM_PRETEND_VERSION = version;

  pythonImportsCheck = [ "mapie" ];

  meta = {
    description = "A scikit-learn-compatible module for estimating prediction intervals";
    homepage = "https://github.com/scikit-learn-contrib/MAPIE";
    license = lib.licenses.bsd3;
  };
}
