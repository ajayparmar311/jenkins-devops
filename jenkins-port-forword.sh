#!/bin/bash
kubectl --namespace jenkins port-forward svc/my-jenkins 8080:8080
wait
