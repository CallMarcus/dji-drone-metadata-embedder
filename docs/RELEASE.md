# Release Process

This project publishes packages to PyPI via GitHub Actions. Pushing a git tag that follows the pattern `vX.Y.Z` triggers the **Release** workflow.

The workflow performs the following steps:

1. Build the wheel and source distribution using `python -m build`.
2. Import a GPG key from the `GPG_PRIVATE_KEY` repository secret.
3. Sign all files in `dist/` with `gpg --detach-sign`.
4. Upload the package to PyPI via the Trusted Publishers flow (OIDC).
5. Attach the artefacts and their signatures to the GitHub release page.

## Creating a Release

1. Update `CHANGELOG.md` and the version in `pyproject.toml`.
2. Commit the changes and create a tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Once the tag is pushed, the workflow will publish the signed packages and attach them to the release page automatically.

## Winget Submission

Winget manifests are published using the `publish-winget.yml` workflow. This workflow
requires a Personal Access Token with permission to submit packages to the
Microsoft Store. Add this token to the repository secrets as `WINGET_PAT` before
running the workflow.
