FROM python:3.9-slim

WORKDIR /app

COPY . .
RUN apt-get update && apt-get install -y sqlite3
RUN pip install -r requirements.txt

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000", "--reload"]
