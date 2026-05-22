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

# Copy entrypoint and normalize line endings.
# If the file was saved on Windows with CRLF, bash inside the Linux container
# would otherwise look for an interpreter literally named `bash\r` and fail.
COPY entrypoint.sh /code/
RUN sed -i 's/\r$//' /code/entrypoint.sh && chmod +x /code/entrypoint.sh
ENTRYPOINT [ "/code/entrypoint.sh" ]

# Copy project
COPY . /code/

# Run the application
CMD ["gunicorn", "e_commerce_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
