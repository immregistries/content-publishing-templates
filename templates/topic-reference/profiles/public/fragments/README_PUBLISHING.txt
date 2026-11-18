Pushing to `main` publishes the guide at {{PAGES_URL}}main/. Pushing a release
tag such as `v0.1.0` publishes it at that version and at
{{PAGES_URL}}latest/.

After each deploy, the workflow saves the guide's build manifest in InteropHub
with the `INTEROPHUB_TOKEN` repository secret, a personal access token with
`topics:write`. A guide is not published until its manifest is saved, so the
workflow fails without the secret.
