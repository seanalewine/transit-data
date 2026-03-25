ARG BUILD_FROM=ghcr.io/home-assistant/base:3.23
FROM ${BUILD_FROM}

ARG TEMPIO_VERSION=2021.09.0
ARG TARGETARCH
RUN \
    if [ -z "${TARGETARCH}" ]; then \
        echo "TARGETARCH is not set, please use Docker BuildKit for the build." && exit 1; \
    fi \
    && case "${TARGETARCH}" in \
        amd64) tempio_arch="amd64" ;; \
        arm64) tempio_arch="aarch64" ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -sSLf -o /usr/bin/tempio \
        "https://github.com/home-assistant/tempio/releases/download/${TEMPIO_VERSION}/tempio_${tempio_arch}"

RUN apk add --no-cache python3

COPY rootfs /

LABEL \
    io.hass.type="addon" \
    org.opencontainers.image.title="Home Assistant App: CTA Train Tracker" \
    org.opencontainers.image.description="Collects CTA train tracking data to monitor train movements." \
    org.opencontainers.image.source="https://github.com/home-assistant/apps-example" \
    org.opencontainers.image.licenses="Apache License 2.0"
