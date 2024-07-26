FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV OPENAI_API_KEY=

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]

