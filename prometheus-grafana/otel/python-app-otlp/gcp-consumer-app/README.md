gcloud auth login
docker build -t us-central1-docker.pkg.dev/my-kube-project-429018/otel-repo-test/otel-bq-loader:1.0.1 .
docker push us-central1-docker.pkg.dev/my-kube-project-429018/otel-repo-test/otel-bq-loader:1.0.1