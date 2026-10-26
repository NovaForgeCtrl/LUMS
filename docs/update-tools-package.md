# Downloadable update-tools package

After the `Tests` workflow passes on `main`, the `Updater package` workflow
creates a `lums-update-tools-<commit>.tar.gz` artifact and a SHA-256 checksum.
Download it from that successful workflow run's **Artifacts** section; build
artifacts are retained for 90 days.

When a GitHub Release is published, the workflow runs the test suite against
the released tag before attaching a versioned `.tar.gz` archive and checksum
to the release. The archive contains the updater scripts and, when present in
that revision, the volume snapshot helper.

This bundle only makes the helper files convenient to download. It is not a
Debian package and does not deploy LUMS. The production updater must pass its
deployment checks and have a verified backup and tested database rollback
before it can replace a running production container.
