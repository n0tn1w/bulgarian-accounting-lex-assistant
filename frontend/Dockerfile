# Stage 1: build the Angular app
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
# Clean install for reproducible builds.
RUN npm ci

COPY . .

# Production build; output lands in dist/frontend/browser/
RUN npm run build -- --configuration production

# Inject the runtime API base so the SPA routes all XHR through the nginx
# /api/ reverse-proxy (same-origin, no CORS complexity).
RUN sed -i 's|</head>|<script>window.__LEDGERLY_API_BASE__="/api";</script></head>|' \
        dist/frontend/browser/index.html


# Stage 2: production nginx
FROM nginx:1.27-alpine

# Remove the default site config.
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
