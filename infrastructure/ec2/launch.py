"""Launch an EC2 instance running the HDB Match backend Docker container.

Run once:
  python infrastructure/ec2/launch.py

The instance pulls the latest image from ECR, starts it, and exposes port 8000.
"""
import boto3
import json
import time

REGION    = "us-west-2"
ECR_IMAGE = "274946909740.dkr.ecr.us-west-2.amazonaws.com/hdb-match-backend:latest"

ec2 = boto3.client("ec2", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)


def ensure_instance_profile() -> str:
    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    })
    try:
        iam.create_role(RoleName="hdb-match-ec2", AssumeRolePolicyDocument=trust)
        for arn in [
            "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
            "arn:aws:iam::aws:policy/AmazonS3FullAccess",
            "arn:aws:iam::aws:policy/AmazonBedrockFullAccess",
        ]:
            iam.attach_role_policy(RoleName="hdb-match-ec2", PolicyArn=arn)
        iam.create_instance_profile(InstanceProfileName="hdb-match-ec2")
        iam.add_role_to_instance_profile(
            InstanceProfileName="hdb-match-ec2", RoleName="hdb-match-ec2"
        )
        print("IAM role created — waiting 15s for propagation...")
        time.sleep(15)
    except iam.exceptions.EntityAlreadyExistsException:
        print("IAM role already exists")
    return "hdb-match-ec2"


def ensure_security_group() -> str:
    try:
        sg = ec2.create_security_group(
            GroupName="hdb-match-backend",
            Description="HDB Match backend"
        )
        sg_id = sg["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {"IpProtocol": "tcp", "FromPort": 8000, "ToPort": 8000,
                 "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "API"}]},
                {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
                 "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH"}]},
            ]
        )
        print(f"Security group created: {sg_id}")
    except ec2.exceptions.ClientError:
        sg_id = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": ["hdb-match-backend"]}]
        )["SecurityGroups"][0]["GroupId"]
        print(f"Security group already exists: {sg_id}")
    return sg_id


def get_latest_ami() -> str:
    images = ec2.describe_images(
        Owners=["amazon"],
        Filters=[
            {"Name": "name", "Values": ["al2023-ami-2023*-x86_64"]},
            {"Name": "state", "Values": ["available"]},
        ]
    )["Images"]
    return sorted(images, key=lambda x: x["CreationDate"], reverse=True)[0]["ImageId"]


USER_DATA = """#!/bin/bash
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker

# Login to ECR using the instance role
aws ecr get-login-password --region {region} \
  | docker login --username AWS --password-stdin \
    274946909740.dkr.ecr.{region}.amazonaws.com

# Pull and run the backend container
docker pull {image}
docker run -d --restart always -p 8000:8000 \
  -e AWS_REGION={region} \
  -e AWS_S3_BUCKET=hdb-match-data \
  -e AWS_BEDROCK_AGENT_ID=RX4UR3WWJH \
  -e AWS_BEDROCK_AGENT_ALIAS_ID=TSTALIASID \
  -e AI_GATEWAY_API_KEY=vck_5I3ZtNIlOKqjFLvmkepmTDgiDsgkoprUwk9kAGoMTCGm6Z1qeP4Aatpe \
  -e LLM_MODEL=google/gemini-2.0-flash \
  -e LLM_PROVIDER=vercel \
  -e ONEMAP_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxNTkyMSwiZm9yZXZlciI6ZmFsc2UsImlzcyI6Ik9uZU1hcCIsImlhdCI6MTc4MDk4Nzk0MiwibmJmIjoxNzgwOTg3OTQyLCJleHAiOjE3ODEyNDcxNDIsImp0aSI6IjQzMjFmMzQ5LTA2M2EtNDMyYi05N2EzLWE0NjFhMDQ5MDBkNyJ9.5ddqfzWKh8qkM9oNqw7hzfLVddQa_qBI_W0IKyLpVzqKOQ4leegS0k9ttk4Ih0MIB0t2XbE-vWwfsrKeD1iUr51iB4DQsqrHS0B2OkfGz-tqYjBAL-v36LsQtD3-Q_-6YGTiBLOdCzJa7N6z048OUEPtlUcJvo3F5e1A6ZqpYaedb_yR-8R7c2zVBiVlFRiF-giJUseZFCi9_5LtrSFntrDNossLVsFYemZ99msNrPHkIHy3F3ITomwnQJzFnOZ6HAfIS6AwJY3oCmPh9a8ABp7sNMCKFtgHn2FQBmwdmz9F2N1nEj-ScjU8ukjudqVr7vUKJ8OkuwRly2rjBkg9XQ \
  -e DATAGOV_API_KEY=v2:7544e283e7008324a7bdad393761cba133044b81a9f42fe769e503541142cc4e:38PIkhFLq--iGVoClxmm5hmtgioU9tsy \
  -e LTA_DATAMALL_API_KEY=+FjeHBYfQ+GBJTJXc/xvAA== \
  {image}
"""


if __name__ == "__main__":
    print("[1/4] Ensuring IAM instance profile...")
    ensure_instance_profile()

    print("[2/4] Ensuring security group...")
    sg_id = ensure_security_group()

    print("[3/4] Finding latest Amazon Linux 2023 AMI...")
    ami_id = get_latest_ami()
    print(f"      AMI: {ami_id}")

    print("[4/4] Launching EC2 instance...")
    resp = ec2.run_instances(
        ImageId=ami_id,
        InstanceType="t3.medium",
        MinCount=1,
        MaxCount=1,
        SecurityGroupIds=[sg_id],
        IamInstanceProfile={"Name": "hdb-match-ec2"},
        UserData=USER_DATA.format(region=REGION, image=ECR_IMAGE),
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "hdb-match-backend"}]
        }],
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    print(f"      Instance ID: {instance_id}")
    print("      Waiting for instance to be running...")

    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
    info = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = info["Reservations"][0]["Instances"][0]["PublicIpAddress"]

    print()
    print("=" * 55)
    print(f"  Instance running: {instance_id}")
    print(f"  Public IP: {public_ip}")
    print()
    print(f"  API URL:    http://{public_ip}:8000")
    print(f"  Health:     http://{public_ip}:8000/health")
    print(f"  API docs:   http://{public_ip}:8000/docs")
    print()
    print("  Docker is starting inside the instance (~2 min).")
    print("  Run: curl http://{ip}:8000/health to confirm.".format(ip=public_ip))
    print("=" * 55)
