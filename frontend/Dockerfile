FROM node:22.14.0-alpine AS dependencies
WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM dependencies AS development

COPY . .

EXPOSE 5173

CMD ["sh", "-c", "pnpm install --frozen-lockfile --force && pnpm dev --host 0.0.0.0"]

FROM dependencies AS build

COPY . .
RUN pnpm build


FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
