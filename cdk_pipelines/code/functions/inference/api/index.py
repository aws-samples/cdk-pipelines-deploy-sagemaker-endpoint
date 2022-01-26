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

from aws_lambda_powertools import Logger
import os
import boto3
import json

"""Initialise Logger class"""
logger = Logger(service="inference_api")

"""Environment Variables"""
ENDPOINT_NAME = os.getenv("ENDPOINT_NAME")

"""Boto3 clients"""
sm = boto3.client("sagemaker-runtime")


@logger.inject_lambda_context(log_event=True)
def handler(event, context):
    """
    Lambda function handler, processes the inputs, tries to invoke the Endpoint and then returns the results
    @param event:
    @param context: context object, not used
    @return: body of the response in case of success, otherwise the exception traceback
    """
    # Fetch resource from event
    resource = event["resource"]

    if resource == "/inference":
        res = sm.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            Body=event["body"],
            ContentType="application/json",
        )
        return {
            "statusCode": 200,
            "headers": {"x-custom-header": "Inference API Response"},
            "body": json.loads(res["Body"].read()),
        }

    # Unknown resource, 404 not found response
    else:
        return {"statusCode": 404, "headers": {"x-custom-header": "Inference API Response"}}
