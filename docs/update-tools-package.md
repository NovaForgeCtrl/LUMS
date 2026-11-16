# Downloadable update-tools package

After the `Tests` workflow passes on `main`, the `Updater package` workflow
creates a `lums-update-tools-<commit>.tar.gz` artifact and a SHA-256 checksum.
Download it from that successful workflow run's **Artifacts** section; build
artifacts are retained for 90 days.

When a GitHub Release is published, the workflow runs the test suite against
the released tag before attaching the updater archive and a deterministic
source archive. The source archive includes its SHA-256 checksum and the
tested commit identifier; the Update Center only lists releases after all
three source-verification assets are present.

The updater-tools bundle is a convenience download, not a Debian package.
The source archive is not installed directly by the web container. Do not use
it to update production until a separately installed host updater has passed
deployment checks and verified both the database backup and rollback behavior
for that exact deployment.
