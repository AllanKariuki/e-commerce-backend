#!/bin/bash

# Wait for Postgres to be ready
until PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -c '\q'; do
  echo "⏳ Waiting for Postgres at $DB_HOST..."
  sleep 2
done

# Create keycloak_db if it doesn't exist
echo "🔍 Checking if keycloak_db exists..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -tc "SELECT 1 FROM pg_database WHERE datname = 'keycloak_db'" | grep -q 1 \
  || PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -c "CREATE DATABASE keycloak_db"

# Django migrations
echo "⚙️ Running Django migrations..."
python manage.py migrate

# Start the app
exec "$@"
