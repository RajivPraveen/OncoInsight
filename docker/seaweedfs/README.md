# `docker/seaweedfs/`: local S3 configuration

[← docker](../README.md)

`s3.json` defines the single S3 identity used by the local SeaweedFS server that stands in for AWS S3 as the raw
layer. These are local-development credentials only. In AWS the bucket is created by
[Terraform](../../infra/terraform/) and accessed through the ECS task role.
