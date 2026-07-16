# Dependency maintenance policy

SignalChord treats dependency changes as release-engineering work. Dependency pull requests are never merged solely because a newer version exists.

## Routine updates

Dependabot checks each supported ecosystem every Monday in the `Europe/Berlin` timezone. Routine version updates are grouped by ecosystem and capped at two open pull requests per ecosystem.

- npm, Go modules, Bundler and GitHub Actions: minor and patch updates only.
- Python: patch updates only because many pre-1.0 packages may introduce incompatible behavior in minor releases.
- Security updates remain enabled independently of the routine version-update limits.

Every dependency pull request must pass the repository's complete test, security, image-build, Helm and end-to-end validation before merge. Dependency pull requests are not auto-merged.

## Major upgrades

Major versions are handled in dedicated migration pull requests. A migration must document:

1. upstream breaking changes and runtime prerequisites;
2. required application, configuration, image or deployment changes;
3. rollback and data-compatibility considerations;
4. focused regression coverage in addition to full CI;
5. successful single-server rendering or acceptance where deployment behavior changes.

Large framework transitions such as Expo, React Native, TypeScript, Rails test tooling, database drivers or GitHub Actions runtimes must not be bundled into an unrelated release.

## Release-line rule

The stable release line prioritizes a reproducible, tested dependency set over immediately adopting every upstream release. Before a stable tag, dependency changes are frozen except for reviewed security fixes or changes required to make the release build and deployment reproducible.

After a stable tag, compatible maintenance updates should be released as patch versions. Major migrations should target the next planned minor or major SignalChord release.
