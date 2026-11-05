# Deployment

GitHub Pages serves the committed dashboard. It reads a versioned HTTPS snapshot from `https://43.166.2.103.sslip.io/nbeta/`. The server's Python batch pipeline builds each snapshot in a new directory, then switches the `current` symlink only after validation succeeds. The dashboard reads `run.json` first and pins all requests to that snapshot version.

On `remote`, application files are in `/home/ubuntu/projects/nbeta/app`; snapshots and ACME certificates are in `/home/ubuntu/projects/nbeta/`. Systemd timers `nbeta-refresh.timer` and `nbeta-cert-renew.timer` run the snapshot build and certificate renewal. The score update runs at 23:00, 23:30 and 00:00 America/Los_Angeles, including daylight-saving changes; later runs catch games delayed by overtime. Nginx serves only the allowed public snapshot paths; CORS is limited to the GitHub Pages origin.

Before each build, ESPN daily scoreboards are queried for a short lookback from the latest completed game through the current Eastern date. Final scores, corrections and newly announced regular-season games are validated and merged into the staged seed; the raw responses and hashes are retained inside each snapshot. Duplicate IDs, invalid scores and matchup conflicts fail the build and retain the previous published snapshot. The displayed `data_through` is the latest completed game, `as_of` is the build time, and `score_checked_at` is the source-check time. The score feed does not update player statistics, player values or injuries; future schedule revisions outside the queried window can remain stale.

Operational checks:

```sh
systemctl status nbeta-refresh.timer nbeta-cert-renew.timer
systemctl status nbeta-refresh.service
journalctl -u nbeta-refresh.service -n 50 --no-pager
curl -fsS https://43.166.2.103.sslip.io/nbeta/data/run.json
```

The certificate is managed by Certbot with a deployment hook that reloads Nginx after successful renewal. The project runs under the `ubuntu` account and uses an isolated virtual environment at `/home/ubuntu/projects/nbeta-venv`.
