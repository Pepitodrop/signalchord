# Release supply chain

SignalChord release artifacts must be built from a protected semantic-version tag that points at a reviewed commit on `main`. Pull-request CI may build and test images, but it must not publish privileged release artifacts.

## Release workflow

The `Release` workflow is the only repository workflow intended to publish application images and GitHub release artifacts. It:

1. verifies the selected tag is `vMAJOR.MINOR.PATCH` and is reachable from `origin/main`;
2. performs frozen installs from committed dependency metadata;
3. builds application images with immutable `sha-<commit>` and release tags;
4. records each pushed image by digest;
5. generates source and final-image SBOMs;
6. scans the source tree and final images for high and critical vulnerabilities;
7. signs image digests with Sigstore keyless signing through GitHub OIDC;
8. verifies image signatures and SLSA provenance attestations before publishing the release;
9. writes `release-manifest.json`, `image-digests.txt`, and `SHA256SUMS`.

High or critical source or final-image findings fail the release unless the release owner documents an approved exception outside the artifact itself. Do not lower the scan severity or `exit-code` to ship a release.

## Digest-only promotion

Production deployment must promote the exact image digests recorded in `release-manifest.json` and `image-digests.txt`. Production must not rebuild images from source, retag mutable references, or deploy a tag without resolving and recording the digest.

Staging promotion evidence must include:

- the release tag and full commit SHA;
- the `release-manifest.json` artifact;
- the rendered deployment values or manifest showing the promoted digests;
- signature and attestation verification output for every image digest;
- source and final-image SBOMs;
- source and final-image vulnerability scan reports.

## Verification

Release signatures are keyless Sigstore signatures issued from GitHub Actions OIDC for `.github/workflows/release.yml`. Verify a release image with:

```bash
cosign verify \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp 'https://github.com/Pepitodrop/signalchord/.github/workflows/release.yml@refs/(tags/v[0-9]+\.[0-9]+\.[0-9]+|heads/main)' \
  ghcr.io/pepitodrop/signalchord-web@sha256:<digest>
```

Verify provenance with:

```bash
cosign verify-attestation \
  --type slsaprovenance \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp 'https://github.com/Pepitodrop/signalchord/.github/workflows/release.yml@refs/(tags/v[0-9]+\.[0-9]+\.[0-9]+|heads/main)' \
  ghcr.io/pepitodrop/signalchord-web@sha256:<digest>
```

The repository helper validates the release manifest shape and rejects mutable image references:

```bash
python3 scripts/release_manifest.py validate --file release-manifest.json
```

## Key management

The current release path uses Sigstore keyless signing. No long-lived signing private key is stored in the repository or in GitHub secrets. The trust root is GitHub OIDC plus Sigstore transparency-log inclusion.

Before production launch, repository administrators must also provide evidence that:

- `main` and release tags are protected;
- only trusted maintainers can approve and run release publishing;
- package publishing permissions are restricted to the release workflow;
- any future keyful signing material, if introduced, is stored in managed KMS/HSM infrastructure with rotation and break-glass procedures.

## External blockers

This repository can enforce reproducible dependency installation, digest-pinned base images, SBOM/scanning artifacts, image signing, provenance verification, and machine-readable manifests. Production approval still requires external evidence for protected branch/tag configuration, registry access controls, staging promotion of the same digests, and formal risk acceptance for any unresolved vulnerability exception.
