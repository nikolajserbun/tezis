FROM node:22-alpine AS build

ARG VITE_API_BASE=
ARG VITE_BOT_USERNAME=tezis_ai_bot
ARG VITE_ADMIN_TELEGRAM_LOGIN=
ARG VITE_DEV_PAYMENTS=true

ENV VITE_API_BASE=$VITE_API_BASE \
    VITE_BOT_USERNAME=$VITE_BOT_USERNAME \
    VITE_ADMIN_TELEGRAM_LOGIN=$VITE_ADMIN_TELEGRAM_LOGIN \
    VITE_DEV_PAYMENTS=$VITE_DEV_PAYMENTS

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json tsconfig.node.json vite.config.ts tailwind.config.js postcss.config.js ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/health >/dev/null || exit 1
