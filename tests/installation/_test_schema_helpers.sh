# SPDX-License-Identifier: Apache-2.0
# Shared helpers for E2E test schema isolation.
# Source this file — do not execute directly.
#
# Provides:
#   setup_test_schema   — create isolated PG schema, re-export DATABASE_URL
#   cleanup_test_schema — drop the schema (safe to call multiple times)
#
# Variables set after setup_test_schema:
#   TEST_SCHEMA_NAME      e.g. e2e_test_1712567890_12345
#   ORIGINAL_DATABASE_URL raw URL before schema qualification
#   SCHEMA_DATABASE_URL   URL with search_path appended

setup_test_schema() {
  : "${DATABASE_URL:?DATABASE_URL must be set}"

  ORIGINAL_DATABASE_URL="$DATABASE_URL"
  TEST_SCHEMA_NAME="e2e_test_$(date +%s)_$$"

  # Drop-then-create (handles leftovers from crashed runs)
  psql "$ORIGINAL_DATABASE_URL" -q -c "DROP SCHEMA IF EXISTS \"${TEST_SCHEMA_NAME}\" CASCADE" >/dev/null
  psql "$ORIGINAL_DATABASE_URL" -q -c "CREATE SCHEMA \"${TEST_SCHEMA_NAME}\"" >/dev/null

  # Create empty alembic_version so Alembic doesn't find the one in public
  psql "$ORIGINAL_DATABASE_URL" -q -c "CREATE TABLE \"${TEST_SCHEMA_NAME}\".alembic_version (version_num VARCHAR(32) NOT NULL)" >/dev/null

  # Build schema-qualified URL (include public for pgvector types)
  if [[ "$ORIGINAL_DATABASE_URL" == *"?"* ]]; then
    SCHEMA_DATABASE_URL="${ORIGINAL_DATABASE_URL}&options=-csearch_path%3D${TEST_SCHEMA_NAME}%2Cpublic"
  else
    SCHEMA_DATABASE_URL="${ORIGINAL_DATABASE_URL}?options=-csearch_path%3D${TEST_SCHEMA_NAME}%2Cpublic"
  fi

  export DATABASE_URL="$SCHEMA_DATABASE_URL"
}

seed_system_data() {
  # Insert the system tenant, BU, and app_user required by CLI commands.
  # Must be called after migrations (tables must exist).
  psql "$SCHEMA_DATABASE_URL" -q <<'SQL' >/dev/null
INSERT INTO tenant (id, name, created_at, updated_at)
  VALUES ('tenant_sys_001', 'System Tenant', now(), now())
  ON CONFLICT (id) DO NOTHING;
INSERT INTO bu (id, tenant_id, name, created_at, updated_at)
  VALUES ('bu_sys_001', 'tenant_sys_001', 'System BU', now(), now())
  ON CONFLICT (id) DO NOTHING;
INSERT INTO app_user (id, email, name, auth_provider_id, created_at, updated_at)
  VALUES ('usr_sys_001', 'system@linkedout.local', 'System Admin', 'system|admin001', now(), now())
  ON CONFLICT (id) DO NOTHING;
SQL
}

cleanup_test_schema() {
  if [ -n "${TEST_SCHEMA_NAME:-}" ] && [ -n "${ORIGINAL_DATABASE_URL:-}" ]; then
    psql "$ORIGINAL_DATABASE_URL" -q -c "DROP SCHEMA IF EXISTS \"${TEST_SCHEMA_NAME}\" CASCADE" >/dev/null 2>&1 || true
  fi
}
