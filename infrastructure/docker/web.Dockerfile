FROM node:22.16.0-alpine AS build
WORKDIR /workspace
RUN corepack enable
COPY package.json pnpm-workspace.yaml turbo.json ./
COPY packages/domain-types ./packages/domain-types
COPY apps/web ./apps/web
RUN pnpm install --frozen-lockfile=false
RUN pnpm --filter @signalchord/web build

FROM nginx:1.28.0-alpine
COPY --from=build /workspace/apps/web/dist /usr/share/nginx/html
COPY infrastructure/docker/web-nginx.conf /etc/nginx/conf.d/default.conf
