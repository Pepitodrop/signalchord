FROM golang:1.26.5-alpine AS build
ARG TARGET
WORKDIR /workspace/services
COPY services/go.mod services/go.sum ./
RUN go mod download
COPY services/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/service ${TARGET}

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/service /service
USER nonroot:nonroot
ENTRYPOINT ["/service"]
