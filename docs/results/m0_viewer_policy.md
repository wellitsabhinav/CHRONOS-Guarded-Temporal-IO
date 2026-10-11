# Viewer deployment policy

Recorded 2026-10-11. Failure class: repository publication configuration.
The M0 viewer job 114521330596 and M1 viewer job 114521944585 generated
their layout files successfully, then failed at Pages deployment with HTTP
404 because GitHub Pages was disabled. GDS generation and physical checks
are separate jobs.

GitHub Pages is now configured to use GitHub Actions as its source. The
user explicitly chose to keep the `github-pages` environment restricted
to `main`, declining deployment from either development branch.
The viewer job therefore runs only on `refs/heads/main`; this matches the
publication policy instead of attempting an unauthorized branch deployment.
The existing main allowlist rule remains. No development branch was added.

GDS, precheck, routed gate tests and logic/documentation qualification
continue on development pushes. No test, assertion, timing target, physical
configuration or official action pin changes. This adjustment affects only
the optional layout publication job, not M0 physical acceptance.

The change was isolated in `fix/m0-viewer-main` from the failing M0 head
`7166d8b6adbe2e87c87f78569074c52d69423f5a`, then merged into M0. M1 receives
it through its baseline update, not through a separate copy of the fix.
After main becomes authoritative, its normal push runs the official viewer.

Primary guidance: [Tiny Tapeout Pages troubleshooting](https://tinytapeout.com/faq/#my-github-action-is-failing-on-the-pages-part)
and [GitHub Pages deployment conditions](https://github.com/actions/deploy-pages#security-considerations).
