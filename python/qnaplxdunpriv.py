#!/usr/bin/env python3
"""Change ACLs for QNAP LXD unprivileged container.
"""

import argparse
import grp
import logging
import os
import pwd
import sys
from typing import Generator, Iterable, Optional, Sequence

from posix1e import (ACL_GROUP, ACL_GROUP_OBJ, ACL_MASK, ACL_USER,
                     ACL_USER_OBJ, ACL_WRITE)
import posix1e

logging.basicConfig(format='%(levelname)s:%(message)s')
_LOGGER = logging.getLogger(__name__)

__version__ = '1.0.0'

STATION_DEFAULT = '/Station'
CONTAINER_DEFAULT = '/Container'

CONTAINER_STATION_PATHS = ('', 'lib', 'var')
CONTAINER_STATION_RECURSE_PATHS = ('usr',)
CONTAINER_PATHS = (
    '',
    'container-station-data/lib',
    'container-station-data/lib/lxd',
    'container-station-data/lib/lxd/containers',
    'container-station-data/lib/lxd/devices',
    'container-station-data/lib/lxd/shmounts',
    'container-station-data/lib/lxd/snapshots',
    'container-station-data/lib/lxd/storage-pools',
    'container-station-data/lib/lxd/storage-pools/default',
    'container-station-data/lib/lxd/storage-pools/default/containers',
)


class FileAclError(Exception):
    """Errors in FileAcl class.
    """


def main(argv: Sequence[str]) -> int:
    """Main function.

    Args:
        argv (Sequence[str]): sequence of arguments

    Returns:
        int: exit code.
    """
    args = _parse_args(argv)
    _LOGGER.setLevel(logging.INFO)
    oper = set_uids if args.op == 'set' else unset_uids
    try:
        for path in _generate_paths(args):
            oper(path, args.uid, dry_run=args.dry_run)
    except FileAclError as ex:
        _LOGGER.error(ex)
        return 1
    _LOGGER.info('Completed')
    return 0


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--dry-run', action='store_true',
        help='print new ACLs without actually changing any files')
    parser.add_argument(
        '--station', default=STATION_DEFAULT,
        help='directory corresponding to Container Station folder '
        'which can be obtained by '
        '"/share/CACHEDEV*_DATA/.qpkg/container-station"')
    parser.add_argument(
        '--container', default=CONTAINER_DEFAULT,
        help='directory corresponding to "/share/Container" shared folder')
    parser.add_argument(
        'op', choices=('set', 'unset'), help='"set" or "unset"')
    parser.add_argument(
        'uid', type=int, nargs='+', help='UID for unprivileged containers')
    return parser.parse_args(argv)


def _generate_paths(args: argparse.Namespace) -> Generator[str, None, None]:
    for path in CONTAINER_STATION_PATHS:
        yield os.path.join(args.station, path)
    for path in CONTAINER_PATHS:
        yield os.path.join(args.container, path)
    for root in CONTAINER_STATION_RECURSE_PATHS:
        for dirpath, _, filenames in os.walk(
                os.path.join(args.station, root)):
            for filename in filenames:
                yield os.path.join(dirpath, filename)
            yield dirpath


def set_uids(path: str, uids: Iterable[int], dry_run: bool = False) -> None:
    """Set permissions for UIDs.

    Args:
        path (str): Target path.
        uids (Iterable[int]): UIDs to set permissions.
        dry_run (bool): Dry run flag.
    """
    file_acl = FileAcl(path)
    file_acl.set_uids(uids, dry_run=dry_run)


def unset_uids(path: str, uids: Iterable[int], dry_run: bool = False) -> None:
    """Unset permissions for UIDs.

    Args:
        path (str): Target path.
        uids (Iterable[int]): UIDs to unset permissions.
        dry_run (bool): Dry run flag.
    """
    file_acl = FileAcl(path)
    file_acl.unset_uids(uids, dry_run=dry_run)


class FileAcl:
    """Class representing the file ACL.
    """
    def __init__(self, path: str) -> None:
        self._path = path
        self._stat = None
        self._acl = None
        if os.path.islink(self.path):
            return
        try:
            self._stat = os.lstat(path)
            self._acl = posix1e.ACL(file=path)
        except OSError as ex:
            raise FileAclError(f'Failed to get info for {path}: {ex}') from ex

    @property
    def path(self) -> str:
        """Target path.

        Returns:
            str: Target path.
        """
        return self._path

    def set_uids(self, uids: Iterable[int], dry_run: bool = False) -> None:
        """Set UIDs.

        Args:
            uids (Iterable[int]): UIDs.
            dry_run (bool): Dry run flag.
        """
        if self._stat is None or self._acl is None:
            return
        group_entry = self._get_group_entry_for_owner()
        owner_user_entry = self._get_entry_by_tag(ACL_USER_OBJ)
        owner_group_entry = self._get_entry_by_tag(ACL_GROUP_OBJ)
        if owner_user_entry is None or owner_group_entry is None:
            raise FileAclError(
                f'Failed to get owner permissions for {self.path}.')
        used_uids = {e.qualifier for e in self._acl if e.tag_type == ACL_USER}
        changed = False
        for uid in uids:
            if uid not in used_uids:
                changed = True
                entry = self._acl.append()
                entry.copy(owner_user_entry)
                entry.tag_type = ACL_USER
                entry.qualifier = uid
                entry.permset.delete(ACL_WRITE)
        if changed:
            if not group_entry:
                group_entry = self._acl.append()
                group_entry.copy(owner_group_entry)
                group_entry.tag_type = ACL_GROUP
                group_entry.qualifier = self._stat.st_gid
            self._apply_acl(dry_run)

    def unset_uids(self, uids: Iterable[int], dry_run: bool = False) -> None:
        """Unset UIDs.

        Args:
            uids (Iterable[int]): UIDs.
            dry_run (bool): Dry run flag.
        """
        if self._acl is None or not posix1e.has_extended(self.path):
            return
        changed = False
        for uid in uids:
            entry = next((e for e in self._acl
                          if e.tag_type == ACL_USER and e.qualifier == uid),
                         None)
            if entry:
                changed = True
                self._acl.delete_entry(entry)
        changed |= self._remove_group_entry_for_owner()
        if changed:
            self._apply_acl(dry_run)

    def _remove_group_entry_for_owner(self) -> bool:
        if self._stat is None or self._acl is None:  # pragma: no cover
            return False
        if os.path.isdir(self.path):
            try:
                default_acl = posix1e.ACL(filedef=self.path)
            except OSError as ex:
                raise FileAclError(
                    f'Failed to get default ACL for {self.path}: {ex}') from ex
            if sum(1 for _ in default_acl):
                return False
        for entry in self._acl:
            if (entry.tag_type == ACL_GROUP
                    and entry.qualifier != self._stat.st_gid
                    or entry.tag_type == ACL_USER):
                return False
        changed = False
        group_entry = self._get_group_entry_for_owner()
        owner_group_entry = self._get_entry_by_tag(ACL_GROUP_OBJ)
        if owner_group_entry is None:
            raise FileAclError(
                f'Failed to get owner group permissions for {self.path}.')
        if group_entry and (str(group_entry.permset)
                            == str(owner_group_entry.permset)):
            changed = True
            self._acl.delete_entry(group_entry)
        mask_entry = self._get_entry_by_tag(ACL_MASK)
        if mask_entry:
            changed |= True
            self._acl.delete_entry(mask_entry)
        return changed

    def _get_group_entry_for_owner(self) -> Optional[posix1e.Entry]:
        return next((
            e for e in self._acl
            if e.tag_type == ACL_GROUP and e.qualifier == self._stat.st_gid),
            None) if self._stat is not None and self._acl is not None else None

    def _get_entry_by_tag(self, tag: int) -> Optional[posix1e.Entry]:
        return next((e for e in self._acl if e.tag_type == tag),
                    None) if self._acl is not None else None

    def _apply_acl(self, dry_run: bool = False) -> None:
        if self._acl is None:  # pragma: no cover
            return
        if next((True for e in self._acl
                 if e.tag_type in {ACL_USER, ACL_GROUP}), False):
            try:
                self._acl.calc_mask()
            except OSError as ex:
                raise FileAclError(
                    f'Failed to calculate mask for {self.path}: {ex}') from ex
        if dry_run:
            self._print_acl()
        else:
            try:
                self._acl.applyto(self.path)
            except OSError as ex:
                raise FileAclError(
                    f'Failed to set ACL for {self.path}: {ex}') from ex

    def _print_acl(self) -> None:
        if self._stat is None or self._acl is None:  # pragma: no cover
            return
        try:
            username = pwd.getpwuid(self._stat.st_uid).pw_name
        except KeyError:
            username = str(self._stat.st_uid)
        try:
            groupname = grp.getgrgid(self._stat.st_gid).gr_name
        except KeyError:
            groupname = str(self._stat.st_gid)
        print(f'# file: {self.path}')
        print(f'# owner: {username}')
        print(f'# group: {groupname}')
        print(self._acl)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
