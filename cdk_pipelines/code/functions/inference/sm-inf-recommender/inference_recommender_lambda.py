# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import json
import os
import tarfile
import boto3
from datetime import datetime, timezone

s3_client = boto3.client("s3")
sm_client = boto3.client("sagemaker")

MODEL_BUCKET = os.environ["MODEL_BUCKET"]
MODEL_URL = os.environ["MODEL_URL"]
MODEL_IMAGE_URI = os.environ["MODEL_IMAGE_URI"]
PROJECT_NAME = os.environ["PROJECT_NAME"]
INFERENCE_RECOMMENDER_ROLE_ARN = os.environ["INFERENCE_RECOMMENDER_ROLE_ARN"]


def handler(event, context):
    # upload the payload to the s3 bucket
    payload_file = "/tmp/payload.json"

    with open(payload_file, "w") as f:
        json.dump(event, f)

    payload_directory = "/tmp/payload.tar.gz"
    with tarfile.open(payload_directory, "w:gz") as tar:
        tar.add(payload_file, arcname=os.path.basename(payload_file))

    s3_client.upload_file(payload_directory, MODEL_BUCKET, payload_directory)

    sample_payload_url = f"s3://{MODEL_BUCKET}/{payload_directory}"

    # create a model package group if non-exist for the projectX
    model_package_group_input_dict = {
        "ModelPackageGroupName": PROJECT_NAME,
        "ModelPackageGroupDescription": f"Model package group for {PROJECT_NAME}",
    }

    try:
        create_model_pacakge_group_response = sm_client.create_model_package_group(**model_package_group_input_dict)
        print("ModelPackageGroup Arn : {}".format(create_model_pacakge_group_response["ModelPackageGroupArn"]))
    except Exception:
        print(f"Model Package Group {PROJECT_NAME} already created")

    print(boto3.__version__)

    # create model package and register the model/payload to the model registry
    model_package_description = f"model package for {PROJECT_NAME}"

    # The supported MIME types for input and output data. In this example,
    # we are using images as input.
    input_content_type = "application/json"
    response_content_type = "application/json"

    model_package_input_dict = {
        "ModelPackageGroupName": PROJECT_NAME,
        "ModelPackageDescription": model_package_description,
        "SamplePayloadUrl": sample_payload_url,
        "Domain": "MACHINE_LEARNING",
        "Task": "OTHER",
        "InferenceSpecification": {
            "Containers": [
                {
                    "Image": MODEL_IMAGE_URI,
                    "ModelDataUrl": MODEL_URL,
                    "Framework": "TENSORFLOW",
                    "FrameworkVersion": "2.0",
                }
            ],
            "SupportedContentTypes": [input_content_type],
            "SupportedResponseMIMETypes": [response_content_type],
        },
    }

    print(model_package_input_dict)

    model_package_response = sm_client.create_model_package(**model_package_input_dict)

    model_package_arn = model_package_response["ModelPackageArn"]

    print("ModelPackage Version ARN : {}".format(model_package_arn))

    # setup timestamp to be used to trigger the custom resource update event to retrieve
    # latest approved model and to be used with model and endpoint config resources' names
    now = datetime.now().replace(tzinfo=timezone.utc)

    timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")

    # Provide a unique job name for SageMaker Inference Recommender job
    job_name = f"{PROJECT_NAME}-{timestamp}"

    # Inference Recommender job type. Set to Default to get an initial recommendation
    job_type = "Default"

    # Provide an IAM Role that gives SageMaker Inference Recommender permission to
    # access AWS services
    role_arn = INFERENCE_RECOMMENDER_ROLE_ARN

    response = sm_client.create_inference_recommendations_job(
        JobName=job_name, JobType=job_type, RoleArn=role_arn, InputConfig={"ModelPackageVersionArn": model_package_arn}
    )

    # job_name = ""

    # response = sm_client.describe_inference_recommendations_job(
    #                 JobName=job_name)

    # print(response['Status'])

    return {
        "statusCode": 200,
        "body": response,
    }
