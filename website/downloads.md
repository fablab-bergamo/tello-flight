# Downloads

Application packages are distributed through **this repository's GitHub Releases**. GitHub Pages hosts
documentation and points to those release assets; the executable runs locally.

The current beta is [v0.1.0-beta.3](https://github.com/fablab-bergamo/tello-flight/releases/tag/v0.1.0-beta.3),
with adjustable command cards and an English/Italian interface.
It is intended for simulator testing and initial hardware evaluation. Physical drone validation remains pending.

When a release exists, download:

| Platform | Asset |
| --- | --- |
| Windows x86-64 | `TelloFlight-windows-x64.zip` |
| Ubuntu 24.04 x86-64 | `TelloFlight-linux-x64.tar.gz` |
| Integrity checks | `SHA256SUMS.txt` |

Use [GitHub Releases](https://github.com/fablab-bergamo/tello-flight/releases) to find published versions
and their assets. Development builds are also available as artifacts on successful
[CI runs](https://github.com/fablab-bergamo/tello-flight/actions/workflows/checks.yml).

Extract the full archive before launching. Windows builds are initially unsigned, so Windows may show
a publisher warning. Compare the SHA-256 digest with the release checksum and download only from
the repository you trust. Signing and wider Linux compatibility are future distribution work.
