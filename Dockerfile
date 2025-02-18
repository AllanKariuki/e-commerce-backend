FROM python:3.12.5-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /code

# Install dependencies
COPY requirements.txt /code/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . /code/

# Run the application
CMD ["gunicorn", "e_commerce_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
