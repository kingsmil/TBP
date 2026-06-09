"""Deploy the PSF forecasting model to a SageMaker real-time endpoint.

Run this script once (or re-run to update the endpoint) after you have:
  1. Exported training data to S3:
       python infrastructure/sagemaker/export_training_data.py
  2. Set environment variables:
       AWS_REGION, AWS_S3_BUCKET, AWS_SAGEMAKER_ROLE_ARN

Usage:
  python infrastructure/sagemaker/deploy_model.py

The script:
  a. Packages train.py + inference.py into a tarball and uploads it to S3.
  b. Creates a SageMaker training job using the managed sklearn container.
  c. Waits for training to finish.
  d. Creates / updates the real-time endpoint (hdb-psf-forecast).
"""
from __future__ import annotations

import io
import os
import tarfile
import time
from datetime import datetime
from pathlib import Path

import boto3

REGION        = os.environ["AWS_REGION"]
BUCKET        = os.environ["AWS_S3_BUCKET"]
ROLE_ARN      = os.environ["AWS_SAGEMAKER_ROLE_ARN"]  # SageMaker execution role
ENDPOINT_NAME = os.getenv("AWS_SAGEMAKER_ENDPOINT", "hdb-psf-forecast")

# ECR image account IDs are region-specific for SageMaker managed containers.
# us-east-1 account is 683313688378. Full list:
# https://docs.aws.amazon.com/sagemaker/latest/dg/pre-built-docker-containers-scikit-learn-spark.html
_SM_SKLEARN_ACCOUNTS = {
    "us-east-1":      "683313688378",
    "us-west-2":      "246618743249",
    "eu-west-1":      "141502667606",
    "ap-southeast-1": "121021644041",
}
_account = _SM_SKLEARN_ACCOUNTS.get(REGION, "683313688378")
SM_SKLEARN_IMAGE = (
    f"{_account}.dkr.ecr.{REGION}.amazonaws.com"
    "/sagemaker-scikit-learn:1.2-1-cpu-py3"
)

sm = boto3.client("sagemaker", region_name=REGION)
s3 = boto3.client("s3",        region_name=REGION)


def _upload_source_tarball() -> str:
    """Bundle train.py + inference.py into sourcedir.tar.gz and upload."""
    here = Path(__file__).parent
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(here / "train.py",     arcname="train.py")
        tar.add(here / "inference.py", arcname="inference.py")
    buf.seek(0)
    key = "sagemaker/source/sourcedir.tar.gz"
    s3.put_object(Bucket=BUCKET, Key=key, Body=buf.read())
    print(f"Source tarball uploaded → s3://{BUCKET}/{key}")
    return f"s3://{BUCKET}/{key}"


def _training_data_s3_uri() -> str:
    return f"s3://{BUCKET}/sagemaker/train/"


def _run_training_job(source_uri: str) -> str:
    """Create a training job and return the S3 URI of the model artifact."""
    job_name = f"hdb-psf-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    print(f"Starting training job: {job_name}")

    sm.create_training_job(
        TrainingJobName=job_name,
        AlgorithmSpecification={
            "TrainingImage":     SM_SKLEARN_IMAGE,
            "TrainingInputMode": "File",
        },
        RoleArn=ROLE_ARN,
        InputDataConfig=[{
            "ChannelName":     "train",
            "DataSource": {
                "S3DataSource": {
                    "S3DataType":             "S3Prefix",
                    "S3Uri":                  _training_data_s3_uri(),
                    "S3DataDistributionType": "FullyReplicated",
                }
            },
        }],
        OutputDataConfig={"S3OutputPath": f"s3://{BUCKET}/sagemaker/output/"},
        ResourceConfig={
            "InstanceType":  "ml.m5.large",
            "InstanceCount": 1,
            "VolumeSizeInGB": 10,
        },
        HyperParameters={
            "sagemaker_program":       "train.py",
            "sagemaker_submit_directory": source_uri,
        },
        StoppingCondition={"MaxRuntimeInSeconds": 900},
    )

    # Wait for the job to finish
    while True:
        status = sm.describe_training_job(TrainingJobName=job_name)["TrainingJobStatus"]
        print(f"  Training job status: {status}")
        if status in ("Completed", "Failed", "Stopped"):
            break
        time.sleep(30)

    if status != "Completed":
        raise RuntimeError(f"Training job {job_name} finished with status: {status}")

    model_artifact = (
        f"s3://{BUCKET}/sagemaker/output/{job_name}/output/model.tar.gz"
    )
    print(f"Training complete. Model artifact: {model_artifact}")
    return model_artifact


def _deploy_endpoint(model_artifact: str) -> None:
    """Create or update the SageMaker endpoint with the new model artifact."""
    model_name = f"hdb-psf-{int(time.time())}"
    config_name = model_name

    sm.create_model(
        ModelName=model_name,
        PrimaryContainer={
            "Image":          SM_SKLEARN_IMAGE,
            "ModelDataUrl":   model_artifact,
            "Environment": {
                "SAGEMAKER_PROGRAM":              "inference.py",
                "SAGEMAKER_SUBMIT_DIRECTORY":     "/opt/ml/model/code",
                "SAGEMAKER_CONTAINER_LOG_LEVEL":  "20",
            },
        },
        ExecutionRoleArn=ROLE_ARN,
    )

    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[{
            "VariantName":         "primary",
            "ModelName":           model_name,
            "InstanceType":        "ml.t3.medium",
            "InitialInstanceCount": 1,
        }],
    )

    try:
        sm.describe_endpoint(EndpointName=ENDPOINT_NAME)
        print(f"Updating existing endpoint: {ENDPOINT_NAME}")
        sm.update_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name,
        )
    except sm.exceptions.ClientError:
        print(f"Creating new endpoint: {ENDPOINT_NAME}")
        sm.create_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name,
        )

    # Wait for endpoint to be in service
    print("Waiting for endpoint to be InService…")
    waiter = sm.get_waiter("endpoint_in_service")
    waiter.wait(EndpointName=ENDPOINT_NAME, WaiterConfig={"Delay": 30, "MaxAttempts": 40})
    print(f"Endpoint '{ENDPOINT_NAME}' is InService.")
    print(f"Set AWS_SAGEMAKER_ENDPOINT={ENDPOINT_NAME} in your environment.")


if __name__ == "__main__":
    source_uri     = _upload_source_tarball()
    model_artifact = _run_training_job(source_uri)
    _deploy_endpoint(model_artifact)
