#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres -v app_password="$(cat /run/secrets/app_password)" -v test_password="$(cat /run/secrets/test_password)" <<'SQL'
CREATE ROLE gov_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'app_password';
CREATE DATABASE gov_package OWNER gov_app;
REVOKE ALL ON DATABASE gov_package FROM PUBLIC;
CREATE ROLE gov_test LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'test_password';
CREATE DATABASE gov_policy_test OWNER gov_test;
REVOKE ALL ON DATABASE gov_policy_test FROM PUBLIC;
\connect gov_package
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
\connect gov_policy_test
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
