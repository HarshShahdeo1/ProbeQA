# Dockerfile (Frontend)
# Multi-stage build for ProbeQA React + Vite Frontend

# ── Stage 1: Build the React Application ──────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests first for optimal Docker layer caching
COPY package*.json ./

# Install dependencies cleanly
RUN npm ci || npm install

# Build argument for backend API URL (defaults to empty string for relative proxy via Nginx)
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Copy application source files
COPY . .

# Build production assets into /app/dist
RUN npm run build

# ── Stage 2: Serve with Production Nginx ──────────────────────────────────────
FROM nginx:alpine

# Remove default Nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration with client-side SPA routing and API reverse proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose standard HTTP port inside container
EXPOSE 80

# Health check to verify Nginx is serving content
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O - http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
