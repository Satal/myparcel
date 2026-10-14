#!/bin/sh
set -e

# Bind-mounted data directories are usually root-owned; give it to the app user,
# then drop root before starting the app.
if [ "$(id -u)" = "0" ]; then
    chown -R myparcel:myparcel /app/data
    exec setpriv --reuid=myparcel --regid=myparcel --init-groups "$@"
fi

exec "$@"
