FROM node:22.16.0-alpine@sha256:41e4389f3d988d2ed55392df4db1420ad048ae53324a8e2b7c6d19508288107e AS build
WORKDIR /workspace
RUN corepack enable
ENV VITE_API_URL="" VITE_REALTIME_URL=""
COPY package.json pnpm-workspace.yaml turbo.json ./
COPY pnpm-lock.yaml ./
COPY packages/domain-types/package.json ./packages/domain-types/package.json
COPY packages/api-client/package.json ./packages/api-client/package.json
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY packages/domain-types ./packages/domain-types
COPY packages/api-client ./packages/api-client
COPY velato ./velato
COPY apps/web ./apps/web
RUN pnpm --filter @signalchord/web build

FROM nginx:1.30.3-alpine3.23@sha256:0d3b80406a13a767339fbe2f41406d6c7da727ab89cf8fae399e81f780f814d1
RUN apk upgrade --no-cache \
 && mkdir -p /tmp/client_temp /tmp/proxy_temp_path /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp \
 && sed -i '/^pid[[:space:]]/d' /etc/nginx/nginx.conf \
 && sed -i '1ipid /tmp/nginx.pid;' /etc/nginx/nginx.conf \
 && sed -i '/^user  nginx;/d' /etc/nginx/nginx.conf \
 && chown -R nginx:nginx /tmp /var/cache/nginx /usr/share/nginx/html
COPY --from=build --chown=nginx:nginx /workspace/apps/web/dist /usr/share/nginx/html
COPY --chown=nginx:nginx infrastructure/docker/web-nginx.conf /etc/nginx/conf.d/default.conf
USER nginx
EXPOSE 8080
ENTRYPOINT []
CMD ["nginx", "-g", "daemon off;"]
