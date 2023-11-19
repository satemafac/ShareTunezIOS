# We'll use a multi-stage build process. Starting with Python base image for Django
FROM python:3.9-slim-buster as backend
WORKDIR /app/backend
COPY /requirements.txt .
RUN apt-get update && apt-get install -y gcc
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY RideTunes/rideTunes .

# Now onto Node base image for React
FROM node:14 as frontend
WORKDIR /app/frontend
COPY RideTunes/rideTunes/frontend/package*.json ./
RUN npm install
COPY RideTunes/rideTunes/frontend .
RUN npm run build

# Now for serving our application, we'll use Nginx
FROM nginx:1.19-alpine
# Copy static files from frontend and backend stages
COPY --from=frontend /app/frontend/build /usr/share/nginx/html
COPY --from=backend /app/backend/static /usr/share/nginx/html/static
# Copy Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf
