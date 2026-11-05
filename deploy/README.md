# Deployment

GitHub Pages serves the committed dashboard. It reads a versioned HTTPS snapshot from `https://43.166.2.103.sslip.io/nbeta/`. The server's Python batch pipeline builds each snapshot in a new directory, then switches the `current` symlink only after validation succeeds. The dashboard reads `run.json` first and pins all requests to that snapshot version.

On `remote`, application files are in `/home/ubuntu/projects/nbeta/app`; snapshots and ACME certificates are in `/home/ubuntu/projects/nbeta/`. Systemd timers `nbeta-refresh.timer` and `nbeta-cert-renew.timer` run the snapshot build and certificate renewal. Nginx serves only the allowed public snapshot paths; CORS is limited to the GitHub Pages origin.

The scheduled build uses the supplied seed. It does **not** refresh game scores, schedules, player values, or injuries. The displayed `data_through` is the last completed game in the seed; `as_of` is the build time. Update and validate the source data separately before rebuilding. The application does not contain a real-time ingestion service.

Operational checks:

```sh
systemctl status nbeta-refresh.timer nbeta-cert-renew.timer
systemctl status nbeta-refresh.service
journalctl -u nbeta-refresh.service -n 50 --no-pager
curl -fsS https://43.166.2.103.sslip.io/nbeta/data/run.json
```

The certificate is managed by Certbot with a deployment hook that reloads Nginx after successful renewal. The project runs under the `ubuntu` account and uses an isolated virtual environment at `/home/ubuntu/projects/nbeta-venv`.
