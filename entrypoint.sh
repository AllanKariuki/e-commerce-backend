#!/bin/bash

# Wait for Postgres to be ready.
# NOTE: the Django side of the project uses DB_PASS, not DB_PASSWORD.
# Accept both so this script keeps working if a future .env adopts
# DB_PASSWORD as the canonical name.
PG_PASS="${DB_PASS:-$DB_PASSWORD}"
until PGPASSWORD=$PG_PASS psql -h $DB_HOST -U $DB_USER -c '\q'; do
  echo "Waiting for Postgres at $DB_HOST..."
  sleep 2
done

# Create keycloak_db if it doesn't exist (belt-and-braces; the init-db.sql
# script in scripts/ also creates it on first boot of an empty pg volume).
echo "Checking if keycloak_db exists..."
PGPASSWORD=$PG_PASS psql -h $DB_HOST -U $DB_USER -tc "SELECT 1 FROM pg_database WHERE datname = 'keycloak_db'" | grep -q 1 \
  || PGPASSWORD=$PG_PASS psql -h $DB_HOST -U $DB_USER -c "CREATE DATABASE keycloak_db"

# Django migrations (only run on web service to avoid race conditions)
if [ "$1" = "gunicorn" ] || [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "🔧 Creating any missing migrations..."
  python manage.py makemigrations --no-input

  echo "🔍 Checking for pending Django migrations..."
  if python manage.py showmigrations | grep '\[ \]'; then
    echo "⚙️ Pending migrations found. Applying migrations..."
  else
    echo "✅ No pending migrations."
  fi

  echo "⚙️ Running Django migrations..."
  python manage.py migrate
else
  echo "🔄 Skipping migrations (not web service)"
fi

# Start the app
exec "$@"
