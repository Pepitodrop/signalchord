FROM node:22.16.0-alpine AS build
WORKDIR /workspace
RUN corepack enable
ENV VITE_API_URL="" VITE_REALTIME_URL=""
COPY package.json pnpm-workspace.yaml turbo.json ./
COPY packages/domain-types ./packages/domain-types
COPY packages/api-client ./packages/api-client
COPY apps/web ./apps/web
RUN pnpm install --frozen-lockfile=false
RUN pnpm --filter @signalchord/web build

FROM nginx:1.28.0-alpine
RUN mkdir -p /tmp/client_temp /tmp/proxy_temp_path /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp \
 && sed -i 's!/var/run/nginx.pid!/tmp/nginx.pid!' /etc/nginx/nginx.conf \
 && sed -i '/^user  nginx;/d' /etc/nginx/nginx.conf \
 && chown -R nginx:nginx /tmp /var/cache/nginx /usr/share/nginx/html
COPY --from=build --chown=nginx:nginx /workspace/apps/web/dist /usr/share/nginx/html
COPY --chown=nginx:nginx infrastructure/docker/web-nginx.conf /etc/nginx/conf.d/default.conf
USER nginx
EXPOSE 8080
ENTRYPOINT []
CMD ["nginx", "-g", "daemon off;"]
