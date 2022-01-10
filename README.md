qnaplxdunpriv
=============

If __Advanced Folder Permissions__ is enabled in [QNAP][] NAS, unprivileged LXD containers won't start. [qnaplxdunpriv][] changes ACLs of some Container Station files to enable running unprivileged LXD containers.

Please make sure to backup your NAS before using this program, and use this program at your own risk.

Usage
-----

Prebuilt Docker image (amd64) to run this program is available at [kobarity/qnaplxdunpriv](https://hub.docker.com/r/kobarity/qnaplxdunpriv). So if you are using amd64 NAS, you can run the image as following:

```sh
docker run -v "$(echo /share/CACHEDEV*_DATA/.qpkg/container-station):/Station" -v /share/Container:/Container --rm kobarity/qnaplxdunpriv set 1000000
```

where the last argument indicates the UID you are going to use for the unprivileged container. The UID can be specified in `security.idmap.base` configuration of LXD containers and defaults to 1000000.

`INFO:Completed` message will be shown if it completes changing ACLs without any errors.

To undo the changes, specify `unset` instead of `set`.

Usage of this program is show below:

```text
usage: qnaplxdunpriv.py [-h] [--dry-run] [--station STATION]
                        [--container CONTAINER]
                        {set,unset} uid [uid ...]

Change ACLs for QNAP LXD unprivileged container.

positional arguments:
  {set,unset}           "set" or "unset"
  uid                   UID for unprivileged containers

options:
  -h, --help            show this help message and exit
  --dry-run             print new ACLs without actually changing any files
                        (default: False)
  --station STATION     directory corresponding to Container Station folder
                        which can be obtained by
                        "/share/CACHEDEV*_DATA/.qpkg/container-station"
                        (default: /Station)
  --container CONTAINER
                        directory corresponding to "/share/Container" shared
                        folder (default: /Container)
```

If you are using ARM architecture NAS or are willing to use your own Docker image, clone the source code from [qnaplxdunpriv][] and build the image under `python` directory as following:

```sh
docker build -t qnaplxdunpriv .
```

Caveat
------

After changing ACLs, users other than `admin` and not in `administrators` group will lose access to files whose ACLs are changed. This is caused by the [QNAP][]'s own implementation of ACLs mentioned in [What's wrong with ACL?][]. In many cases, this should not be a problem because users other than `admin` and not in `administrators` group typically do not need to access these files. However, if you need to grant access to some users or groups, a workaround is to add ACL entries explicitly allows the users or groups to access these files.

Background
----------

Marco Trevisan kindly provided a script to change ACLs to enable running unprivileged LXD containers in [Failing to start unprivileged container (QNAP)][] thread. However, simply adding an ACL entry would result in users other than `admin` (including users in `administrators` group) being unable to execute commands such as `docker` or `lxc` due to the [QNAP][]'s own implementation of ACLs mentioned in [What's wrong with ACL?][].

To address this issue, this program processes ACLs for `set` operation:

1. If ACL entries explicitly specifying the given UIDs do not exist, create ACL entries explicitly specifying the given UIDs with permissions same as owner user excluding write permission.
2. If an ACL entry explicitly specifying the owner group does not exist, create an ACL entry explicitly specifying the owner group with permissions same as owner group.
3. If the ACL is changed, calculate the mask entry.

On the other hand, this program processes ACLs for `unset` operation:

1. Remove ACL entries explicitly specifying the given UIDs.
2. If an ACL entry explicitly specifying a user, an ACL entry explicitly specifying a group other than the owner group, or a default ACL entry exists, finish processing the file.
3. Otherwise, if an ACL entry explicitly specifying the owner group exists and its permissions match the permissions of the owner group ACL entry, remove the ACL entry explicitly specifying the owner group.
4. Remove the mask entry.
5. If an ACL entry explicitly specifying a user or a group exists, calculate the mask entry.

Bash script
-----------

A Bash script `qnap-lxd-unpriv.sh` is located under `bash` directory. It functions nearly same as the above mentioned program, however it should be considered as a prototype for reference purposes because:

- it is much slower than the Python version. It takes a few minutes (SSD on TS-453D) while the Python version runs in a few seconds.
- it accepts only one UID.
- it is not tested as the Python version.

Contributing
------------

Please [open a new issue](https://github.com/kobarity/qnaplxdunpriv/issues/new) if you find a problem. Pull requests are also welcome.

Licenses
--------

Copyright 2022 kobarity

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

<http://www.apache.org/licenses/LICENSE-2.0>

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

[qnaplxdunpriv]:https://github.com/kobarity/qnaplxdunpriv/
[QNAP]:https://www.qnap.com/
[What's wrong with ACL?]:https://forum.qnap.com/viewtopic.php?t=97402
[Failing to start unprivileged container (QNAP)]:https://discuss.linuxcontainers.org/t/failing-to-start-unprivileged-container-qnap/12235/9
