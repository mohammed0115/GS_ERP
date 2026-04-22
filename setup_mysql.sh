#!/usr/bin/env bash
# Run this once to create the MySQL database and user for GS ERP.
# Usage: sudo bash setup_mysql.sh
set -e

echo "Creating MySQL database and user for GS ERP..."

mysql -u root << 'SQL'
CREATE DATABASE IF NOT EXISTS gs_erp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'gs_erp'@'localhost' IDENTIFIED BY 'gs_erp_pass';
CREATE USER IF NOT EXISTS 'gs_erp'@'127.0.0.1' IDENTIFIED BY 'gs_erp_pass';

GRANT ALL PRIVILEGES ON gs_erp.* TO 'gs_erp'@'localhost';
GRANT ALL PRIVILEGES ON gs_erp.* TO 'gs_erp'@'127.0.0.1';

FLUSH PRIVILEGES;

SELECT 'GS ERP database and user created successfully.' AS status;
SQL

echo "Done. You can now run: .venv/bin/python manage.py migrate"
