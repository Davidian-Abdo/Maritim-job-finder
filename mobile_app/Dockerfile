############################
# Stage 1: Build Flutter Web
############################
FROM cirrusci/flutter:stable AS builder

WORKDIR /app

COPY . .

RUN flutter config --enable-web
RUN flutter pub get

ARG API_URL
ENV API_URL=$API_URL

RUN flutter build web \
  --web-renderer html \
  --dart-define=API_URL=$API_URL

############################
# Stage 2: Nginx Server
############################
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/build/web /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
