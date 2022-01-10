"""Tests for qnaplxdunpriv.py
"""

# pylint: disable=missing-function-docstring

import grp
import os
import pathlib
import pwd
import re
import subprocess

import pytest

from qnaplxdunpriv import FileAclError, set_uids, unset_uids
import qnaplxdunpriv

_TEST_UID = 10000
_TEST_FILE = 'file'
_OWNER_GROUP_RE = re.compile(r'^group::([r-][w-][x-])$', re.MULTILINE)


@pytest.mark.parametrize('mode,user_perms,group_perms', [
    ('770', 'r-x', 'rwx'), ('640', 'r--', 'r--')])
def test_set_unset_uids_file(uids: list[int], target_file: str, mode: str,
                             user_perms: str, group_perms: str) -> None:
    owner_gid = os.stat(target_file).st_gid
    subprocess.run(('chmod', mode, target_file), check=True)
    set_uids(target_file, uids)
    result = subprocess.run(
        ('getfacl', '-nps', target_file), capture_output=True, check=True)
    for uid in uids:
        assert f'user:{uid}:{user_perms}'.encode() in result.stdout
    assert f'group:{owner_gid}:{group_perms}'.encode() in result.stdout
    unset_uids(target_file, uids)
    result = subprocess.run(
        ('getfacl', '-nps', target_file), capture_output=True, check=True)
    assert result.stdout == b''


def test_set_uids_not_exist(tmp_path: pathlib.Path) -> None:
    target_file = str(tmp_path / 'not_exist')
    with pytest.raises(FileAclError) as excinfo:
        set_uids(target_file, [_TEST_UID])
    assert 'No such file or directory' in str(excinfo.value)


def test_set_uids_link(target_symlink: str) -> None:
    set_uids(target_symlink, [_TEST_UID])
    result = subprocess.run(
        ('getfacl', '-nps', target_symlink), capture_output=True, check=True)
    assert result.stdout == b''


def test_set_uids_link_ne(target_symlink_ne: str) -> None:
    set_uids(target_symlink_ne, [_TEST_UID])


@pytest.mark.parametrize('mode,user_perms,group_perms', [
    ('770', 'r-x', 'rwx'), ('640', 'r--', 'r--')])
def test_set_uids_dry_run(
        target_file: str, capsys: pytest.CaptureFixture, mode: str,
        user_perms: str, group_perms: str) -> None:
    owner_gid = os.stat(target_file).st_gid
    try:
        user_name = pwd.getpwuid(_TEST_UID).pw_name.replace(' ', '\\040')
    except KeyError:
        user_name = str(_TEST_UID)
    try:
        group_name = grp.getgrgid(owner_gid).gr_name.replace(' ', '\\040')
    except KeyError:
        group_name = str(owner_gid)
    subprocess.run(('chmod', mode, target_file), check=True)
    set_uids(target_file, [_TEST_UID], dry_run=True)
    output = capsys.readouterr().out
    assert f'# file: {target_file}' in output
    assert '# owner: ' in output
    assert '# group: ' in output
    assert f'user:{user_name}:{user_perms}' in output
    assert f'group:{group_name}:{group_perms}' in output
    result = subprocess.run(
        ('getfacl', '-nps', target_file), capture_output=True, check=True)
    assert result.stdout == b''


@pytest.mark.parametrize('user', [
    [],
    ['-m', f'user:{_TEST_UID}:r--'],
])
def test_unset_uids_file(target_file: str, user: list[str]) -> None:
    owner_gid = os.stat(target_file).st_gid
    owner_group_perms = _get_owner_group_perms(target_file)
    group_args: list[list[str]] = [
        [], ['-m', f'group:{owner_gid}:{owner_group_perms}']]
    for group in group_args:
        args = user + group
        if args:
            subprocess.run(['setfacl'] + args + [target_file], check=True)
        unset_uids(target_file, [_TEST_UID])
        result = subprocess.run(
            ('getfacl', '-nps', target_file), capture_output=True, check=True)
        assert result.stdout == b''


def test_unset_uids_file_2(target_file: str) -> None:
    owner_gid = os.stat(target_file).st_gid
    subprocess.run((
        'setfacl', '-m', f'user:{_TEST_UID}:r--',
        '-m', f'user:{_TEST_UID * 2}:r--', '-m', f'group:{owner_gid}:r--',
        target_file), check=True)
    unset_uids(target_file, [_TEST_UID])
    result = subprocess.run(
        ('getfacl', '-nps', target_file), capture_output=True, check=True)
    assert f'user:{_TEST_UID}:r--'.encode() not in result.stdout
    assert f'user:{_TEST_UID * 2}:r--'.encode() in result.stdout
    assert f'group:{owner_gid}:r--'.encode() in result.stdout


def test_unset_uids_file_different_perms(target_file: str) -> None:
    owner_gid = os.stat(target_file).st_gid
    owner_group_perms = _get_owner_group_perms(target_file)
    group_perms = 'r-x' if owner_group_perms != 'r-x' else 'r--'
    subprocess.run((
        'setfacl', '-m', f'user:{_TEST_UID}:r--',
        '-m', f'group:{owner_gid}:{group_perms}',
        target_file), check=True)
    unset_uids(target_file, [_TEST_UID])
    result = subprocess.run(
        ('getfacl', '-nps', target_file), capture_output=True, check=True)
    assert f'user:{_TEST_UID}:r--'.encode() not in result.stdout
    assert f'group:{owner_gid}:{group_perms}'.encode() in result.stdout


def test_unset_uids_default(target_dir: str) -> None:
    subprocess.run((
        'setfacl', '-m', 'default:user::r--', target_dir), check=True)
    unset_uids(target_dir, [_TEST_UID])
    result = subprocess.run(
        ('getfacl', '-nps', target_dir), capture_output=True, check=True)
    assert 'default:user::r--'.encode() in result.stdout


def test_unset_uids_not_exist(tmp_path: pathlib.Path) -> None:
    target_file = str(tmp_path / 'not_exist')
    with pytest.raises(FileAclError) as excinfo:
        unset_uids(target_file, [_TEST_UID])
    assert 'No such file or directory' in str(excinfo.value)


def test_unset_uids_link(target_symlink: str) -> None:
    owner_gid = os.stat(target_symlink).st_gid
    subprocess.run((
        'setfacl', '-m', f'user:{_TEST_UID}:r--',
        '-m', f'group:{owner_gid}:r--', target_symlink), check=True)
    before = subprocess.run(
        ('getfacl', '-nps', target_symlink), capture_output=True, check=True)
    unset_uids(target_symlink, [_TEST_UID])
    after = subprocess.run(
        ('getfacl', '-nps', target_symlink), capture_output=True, check=True)
    assert before.stdout == after.stdout


def test_unset_uids_link_ne(target_symlink_ne: str) -> None:
    unset_uids(target_symlink_ne, [_TEST_UID])


def test_main(tmp_path: pathlib.Path) -> None:
    station_root = tmp_path / qnaplxdunpriv.STATION_DEFAULT.lstrip('/')
    station_root.mkdir(parents=True)
    for dir_name in (qnaplxdunpriv.CONTAINER_STATION_PATHS
                     + qnaplxdunpriv.CONTAINER_STATION_RECURSE_PATHS):
        _make_files(station_root, dir_name)
    container_root = tmp_path / qnaplxdunpriv.CONTAINER_DEFAULT.lstrip('/')
    container_root.mkdir()
    for dir_name in qnaplxdunpriv.CONTAINER_PATHS:
        _make_files(container_root, dir_name)
    ret = qnaplxdunpriv.main([
        '--station', str(station_root), '--container', str(container_root),
        'set', str(_TEST_UID)])
    assert ret == 0
    for dir_name in qnaplxdunpriv.CONTAINER_STATION_PATHS:
        dir_path = station_root / dir_name
        _assert_extended_acl(dir_path)
        if dir_name:
            _assert_base_acl(dir_path / _TEST_FILE)
    for dir_name in qnaplxdunpriv.CONTAINER_STATION_RECURSE_PATHS:
        dir_path = station_root / dir_name
        _assert_extended_acl(dir_path)
        if dir_name:
            _assert_extended_acl(dir_path / _TEST_FILE)
    for dir_name in qnaplxdunpriv.CONTAINER_PATHS:
        dir_path = container_root / dir_name
        _assert_extended_acl(dir_path)
        if dir_name:
            _assert_base_acl(dir_path / _TEST_FILE)
    ret = qnaplxdunpriv.main([
        '--station', str(station_root), '--container', str(container_root),
        'unset', str(_TEST_UID)])
    assert ret == 0
    result = subprocess.run(
        ('getfacl', '-Rnps', str(tmp_path)), capture_output=True, check=True)
    assert result.stdout == b''


def _make_files(root: pathlib.Path, dir_name: str) -> None:
    if not dir_name:
        return
    dir_path = root / dir_name
    dir_path.mkdir(parents=True)
    file_path = dir_path / _TEST_FILE
    file_path.write_text('contents')


def _assert_extended_acl(path: pathlib.Path) -> None:
    assert _getfacl(path)


def _assert_base_acl(path: pathlib.Path) -> None:
    assert not _getfacl(path)


def _getfacl(path: pathlib.Path) -> bytes:
    retult = subprocess.run(
        ('getfacl', '-nps', str(path)), capture_output=True, check=True)
    return retult.stdout


def test_main_error() -> None:
    with pytest.raises(SystemExit) as ex:
        qnaplxdunpriv.main([])
    assert ex.value.code != 0


def _get_owner_group_perms(target_file: str) -> str:
    result = subprocess.run(
        ('getfacl', '-np', target_file), capture_output=True, check=True)
    match = _OWNER_GROUP_RE.search(result.stdout.decode())
    if not match:
        pytest.fail('Failed to get owner group permissions.')
    return match.group(1)
