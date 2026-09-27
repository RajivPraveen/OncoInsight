terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
  # Remote state (create the bucket/table once, then uncomment):
  # backend "s3" {
  #   bucket         = "oncoinsight-tfstate"
  #   key            = "oncoinsight/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "oncoinsight-tflock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "oncoinsight"
      Environment = var.environment
      DataClass   = "public-deidentified-research"
      ManagedBy   = "terraform"
    }
  }
}
