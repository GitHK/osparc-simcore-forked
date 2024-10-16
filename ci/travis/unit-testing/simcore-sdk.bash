#!/bin/bash
set -o errexit  # abort on nonzero exitstatus
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes
IFS=$'\n\t'

# in case it's a Pull request, the env are never available, default to itisfoundation to get a maybe not too old version for caching
DOCKER_IMAGE_TAG=$(exec ci/helpers/build_docker_image_tag.bash)
export DOCKER_IMAGE_TAG

FOLDER_CHECKS=(packages/ simcore-sdk storage/ simcore-sdk .travis.yml)

before_install() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    bash ci/travis/helpers/update-docker.bash
    bash ci/travis/helpers/install-docker-compose.bash
    bash ci/helpers/show_system_versions.bash
  fi
}

install() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    bash ci/helpers/ensure_python_pip.bash
    pushd packages/simcore-sdk
    pip3 install -r requirements/ci.txt
    popd
  fi
}

before_script() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    pip list -v
  fi
}

script() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    pytest --log-format="%(asctime)s %(levelname)s %(message)s" \
      --log-date-format="%Y-%m-%d %H:%M:%S" \
      --cov=simcore_sdk --durations=10 --cov-append \
      --color=yes --cov-report=term-missing --cov-report=xml --cov-config=.coveragerc \
      -v -m "not travis" packages/simcore-sdk/tests/unit

  else
    echo "No changes detected. Skipping integration-testing of simcore-sdk."
  fi
}

after_success() {
  if bash ci/travis/helpers/test-for-changes.bash "${FOLDER_CHECKS[@]}"; then
    coveralls
  fi
}

after_failure() {
  docker images
}

# Check if the function exists (bash specific)
if declare -f "$1" >/dev/null; then
  # call arguments verbatim
  "$@"
else
  # Show a helpful error
  echo "'$1' is not a known function name" >&2
  exit 1
fi
