#!/bin/bash
set -eu

# Change these values to match your configuration!
: "${CONTAINER_FOLDER:=Container}"

CONTAINER_PATH=$(readlink -f "/share/${CONTAINER_FOLDER}")
CONTAINER_VOLUME=${CONTAINER_PATH%/*}

PATHS=(
    "$CONTAINER_VOLUME/.qpkg/container-station"
    "$CONTAINER_VOLUME/.qpkg/container-station/lib"
    "$CONTAINER_VOLUME/.qpkg/container-station/var"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib/lxd"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib/lxd/containers"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib/lxd/devices"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib/lxd/shmounts"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib/lxd/snapshots"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib/lxd/storage-pools"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib/lxd/storage-pools/default"
    "$CONTAINER_VOLUME/${CONTAINER_FOLDER}/container-station-data/lib/lxd/storage-pools/default/containers"
)
RPATHS=(
    "$CONTAINER_VOLUME/.qpkg/container-station/usr"
)

GROUP_RE="^# group: (.+)$"
OWNER_USER_RE="^user::([rwx-]+)$"
OWNER_GROUP_RE="^group::([rwx-]+)$"
IGNORE_RE="^($|#|(user|mask|other)::)"

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Use as $0 [set|unset] <UID>"
  exit 1
fi

userid="$2"

set_acl() {
    local owner_user_perms owner_group owner_group_perms
    owner_user_perms=
    owner_group=
    owner_group_perms=
    while IFS= read -r line; do
        if [[ "${line}" =~ ${OWNER_USER_RE} ]]; then
            owner_user_perms="${BASH_REMATCH[1]}"
        elif [[ "${line}" =~ ${GROUP_RE} ]]; then
            owner_group="${BASH_REMATCH[1]}"
        elif [[ "${line}" =~ ${OWNER_GROUP_RE} ]]; then
            owner_group_perms="${BASH_REMATCH[1]}"
        fi
        if [[ -n "${owner_user_perms}" && -n "${owner_group}" && -n "${owner_group_perms}" ]]; then
            break
        fi
    done < <(getfacl -p "$1")
    if [[ -z "${owner_user_perms}" || -z "${owner_group}" || -z "${owner_group_perms}" ]]; then
        echo "Unexpected ACL in $1, skip it."
        return 0
    fi
    setfacl -m "user:${userid}:${owner_user_perms//w/-}" -m "group:${owner_group}:${owner_group_perms}" "$1"
}

unset_acl() {
    local line group_re group_perms owner_group_perms
    setfacl -x "user:${userid}" "$1"
    group_re=
    group_perms=
    owner_group_perms=
    while IFS= read -r line; do
        if [[ -z "${group_re}" && "${line}" =~ ${GROUP_RE} ]]; then
            group_re="^group:${BASH_REMATCH[1]}:([rwx-]+)$"
        elif [[ -n "${group_re}" && "${line}" =~ ${group_re} ]]; then
            group_perms="${BASH_REMATCH[1]}"
        elif [[ "${line}" =~ ${OWNER_GROUP_RE} ]]; then
            owner_group_perms="${BASH_REMATCH[1]}"
        elif [[ "${line}" =~ ${IGNORE_RE} ]]; then
            continue
        else
            return 0
        fi
        if [[ -n "${group_perms}" && -n "${owner_group_perms}" && "${group_perms}" != "${owner_group_perms}" ]]; then
            return 0
        fi
    done < <(getfacl -sp "$1")
    if [ -n "${group_perms}" ]; then
        setfacl -b "$1"
    fi
}

if [ "$1" = "set" ]; then
    for path in "${PATHS[@]}"; do
        set_acl "${path}"
    done
    for root in "${RPATHS[@]}"; do
        while IFS= read -r -d '' path; do
            set_acl "${path}"
        done < <(find "${root}" ! -type l -print0)
    done
elif [ "$1" = "unset" ]; then
    for path in "${PATHS[@]}"; do
        unset_acl "${path}"
    done
    for root in "${RPATHS[@]}"; do
        while IFS= read -r path; do
            unset_acl "${path}"
        done < <(getfacl -Rsp "${root}" | sed -n 's/^# file: //p')
    done
else
  echo "Invalid operation"
  exit 1
fi
echo "Completed"
