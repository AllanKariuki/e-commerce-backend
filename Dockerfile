FROM python:3.12

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /code

# Install dependencies
COPY requirements.txt /code/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install PostgreSQL client
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy project. entrypoint.sh comes with it; we normalize line endings
# AFTER the full copy below so the CRLF-stripping doesn't get clobbered
# by this COPY (which was the bug behind a 2026-05-24 boot failure —
# the normalization used to run *before* `COPY . /code/`, so the CRLF
# version from the build context overwrote the cleaned copy).
COPY . /code/

# Normalize line endings on the entrypoint. If the project was checked
# out on Windows with CRLF, bash inside the Linux container would
# otherwise look for an interpreter literally named `bash\r` and fail
# with `exec /code/entrypoint.sh: no such file or directory` — which
# is misleading because the file IS there, just unreadable.
RUN sed -i 's/\r$//' /code/entrypoint.sh && chmod +x /code/entrypoint.sh
ENTRYPOINT [ "/code/entrypoint.sh" ]

# Run the application
CMD ["gunicorn", "e_commerce_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
