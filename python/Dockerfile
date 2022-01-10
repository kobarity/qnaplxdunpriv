FROM alpine:edge

LABEL maintainer="kobarity" \
    description="Change ACLs for QNAP LXD unprivileged container."

COPY qnaplxdunpriv.py /usr/local/bin
# hadolint ignore=DL3018
RUN chmod 755 /usr/local/bin/qnaplxdunpriv.py && \
    apk add --no-cache --repository=http://dl-cdn.alpinelinux.org/alpine/edge/testing/ \
    python3 \
    py3-libacl

ENTRYPOINT [ "/usr/local/bin/qnaplxdunpriv.py" ]
