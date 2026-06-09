"""Centralised boto3 client factory.

Credentials are picked up automatically in this priority order:
  1. IAM role attached to the ECS task (production — no keys needed)
  2. AWS SSO session via AWS_PROFILE (local dev with Kiro Identity Center)
       → run `aws sso login --profile kiro-pro` before starting the server
  3. Environment variables AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (CI fallback)
  4. ~/.aws/credentials (static key fallback)

Never hardcode credentials here or anywhere else in the codebase.
"""
from __future__ import annotations

import functools
import os
from typing import Any

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

AWS_REGION  = os.getenv("AWS_REGION", "us-west-2")

_RETRY_CONFIG = Config(retries={"max_attempts": 3, "mode": "standard"})


def _session() -> boto3.Session:
    """Return a boto3 Session.

    Credential priority (boto3 standard):
      1. ECS task IAM role (production)
      2. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN env vars (local/CI)
      3. AWS_PROFILE / ~/.aws (SSO fallback)
    """
    profile = os.getenv("AWS_PROFILE", "")
    if profile:
        return boto3.Session(profile_name=profile, region_name=AWS_REGION)
    return boto3.Session(region_name=AWS_REGION)


@functools.lru_cache(maxsize=None)
def get_s3() -> Any:
    return _session().client("s3", config=_RETRY_CONFIG)


@functools.lru_cache(maxsize=None)
def get_bedrock_runtime() -> Any:
    return _session().client("bedrock-runtime", config=_RETRY_CONFIG)


@functools.lru_cache(maxsize=None)
def get_sagemaker_runtime() -> Any:
    return _session().client("sagemaker-runtime", config=_RETRY_CONFIG)


@functools.lru_cache(maxsize=None)
def get_bedrock_agent_runtime() -> Any:
    return _session().client("bedrock-agent-runtime", config=_RETRY_CONFIG)
