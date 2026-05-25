# Frontend React/Vite do CompStat Rio — multistage build + nginx.
#
# Build (a partir da raiz do repo, para preservar contexto enxuto):
#   docker build -t compstat-frontend -f app/frontend/Dockerfile app/frontend
#
# O nginx do estágio final faz proxy de /api -> backend:8010 (ver nginx.conf).

# ---------- estágio de build ----------
FROM node:20-alpine AS build

WORKDIR /app

# Camada de deps separada para cache.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite ignora process.env do shell; injetar via build-arg se necessário.
RUN npm run build

# ---------- estágio de runtime ----------
FROM nginx:1.27-alpine AS runtime

# Substitui a config default por uma que faz proxy de /api e serve SPA.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1
