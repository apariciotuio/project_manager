# syntax=docker/dockerfile:1

# ---- base ----
FROM node:20-alpine AS base
WORKDIR /app

# ---- dev ----
FROM base AS dev
COPY package.json package-lock.json* ./
RUN npm ci
# Source is mounted at runtime via volume (docker-compose)
EXPOSE 17005
CMD ["npm", "run", "dev"]
