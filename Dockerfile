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
RUN apt-get update && apt-get install -y postgresql-client dos2unix && rm -rf /var/lib/apt/lists/*
# Copy entrypoint
COPY entrypoint.sh /code/
# Fix line endings and make executable
RUN dos2unix /code/entrypoint.sh && chmod +x /code/entrypoint.sh
ENTRYPOINT [ "/code/entrypoint.sh" ]
# Copy project
COPY . /code/
# Run the application
CMD ["gunicorn", "e_commerce_backend.wsgi:application", "--bind", "0.0.0.0:8000"]


# FROM python:3.12

# # Set environment variables
# ENV PYTHONDONTWRITEBYTECODE 1
# ENV PYTHONUNBUFFERED 1

# # Set work directory
# WORKDIR /code

# # Install dependencies
# COPY requirements.txt /code/
# RUN pip install --upgrade pip && pip install -r requirements.txt

# # Install PostgreSQL client
# RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# # Copy entrypoint
# COPY entrypoint.sh /code/
# RUN chmod +x /code/entrypoint.sh
# ENTRYPOINT [ "/code/entrypoint.sh" ]

# # Copy project
# COPY . /code/

# # Run the application
# CMD ["gunicorn", "e_commerce_backend.wsgi:application", "--bind", "0.0.0.0:8000"]

