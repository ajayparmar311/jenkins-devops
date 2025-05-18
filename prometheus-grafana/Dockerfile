FROM mysql:8.0

# Install wget and vim using microdnf (lightweight DNF for slim images)
RUN microdnf update -y && \
    microdnf install -y vim wget && \
    microdnf clean all

