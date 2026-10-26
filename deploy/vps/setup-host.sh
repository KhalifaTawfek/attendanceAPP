#!/bin/sh
# One-time host setup (run with sudo): nginx site + HTTPS certificate.
set -e
cp "$(dirname "$0")/nginx-host.conf" /etc/nginx/sites-available/attendance
ln -sf /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/attendance
nginx -t
systemctl reload nginx
certbot --nginx -d attendance.cookblog.net --non-interactive --agree-tos --redirect --register-unsafely-without-email
systemctl reload nginx
echo "Done: https://attendance.cookblog.net"
