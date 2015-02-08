#!/bin/bash

SLICER_SUPERBUILD="${HOME}/slicer4/latest/Slicer-superbuild"
if [ -e ${SLICER_SUPERBUILD} ]; then
  SLICER_BUILD="${SLICER_SUPERBUILD}/Slicer-build"
  SLICER_BUILD="${SLICER_SUPERBUILD}/Slicer-build"
  PYTHONEXE="${SLICER_SUPERBUILD}/python-build/bin/python"
  LAUNCH="${SLICER_BUILD}/Slicer --launcher-no-splash --launch"
  PYTHON="${LAUNCH} ${PYTHONEXE}"
fi


tmpdir=`mktemp -d /tmp/slicercl.XXXX`
cd ${tmpdir}
git clone https://github.com/djc/couchdb-python.git
cd couchdb-python
git checkout 0.9
${PYTHON} setup.py install

echo
echo
echo "Built in ${tmpdir}"

echo "optionally, run this to install in the application:"
echo
echo "(cd ${tmpdir} ; /Applications/Slicer-4.4.0.app/Contents/MacOS/Slicer setup.py install)"
