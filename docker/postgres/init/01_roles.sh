#!/bin/sh
# Runs once on first container start. Creates:
#  * a separate database for Dagster run/event storage
#  * a least-privilege read-only role used by the API, dashboard and AI assistant. It can only read
#    the curated schemas (marts, analytics, ops) - never raw FHIR / staging tables.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  create database dagster;
  do \$\$ begin
    if not exists (select from pg_roles where rolname = 'onco_reader') then
      create role onco_reader login password '${ONCO_READER_PASSWORD:-onco_reader}';
    end if;
  end \$\$;
  alter role onco_reader set statement_timeout = '30s';
  alter role onco_reader set default_transaction_read_only = on;
  grant connect on database ${POSTGRES_DB} to onco_reader;
  create schema if not exists raw;
  create schema if not exists ops;
  create schema if not exists analytics;
  create schema if not exists marts;
  grant usage on schema marts, analytics, ops to onco_reader;
  alter default privileges for role ${POSTGRES_USER} in schema marts grant select on tables to onco_reader;
  alter default privileges for role ${POSTGRES_USER} in schema analytics grant select on tables to onco_reader;
  alter default privileges for role ${POSTGRES_USER} in schema ops grant select on tables to onco_reader;
EOSQL
