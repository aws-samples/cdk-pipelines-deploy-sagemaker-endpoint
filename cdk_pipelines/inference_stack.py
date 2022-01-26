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

from aws_cdk import (
    Aws,
    Duration,
    Stack,
    Stage,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_apigateway as api_gateway,
    aws_logs as logs,
    aws_kms as kms,
)

from aws_cdk.aws_lambda_python_alpha import PythonFunction, PythonLayerVersion
import constructs
from cdk_pipelines.config.constants import (
    APP_PREFIX,
    LAMBDA_FUNCTION_ENTRY,
    MODEL_PACKAGE_GROUP_NAME,
)

import importlib


class InferenceStack(Stack):
    """
    Inference Stack
    Inference stack which provisions resources required to make inference to SageMaker Endpoint this includes a lambda function and an API Gateway endpoint.
    """

    def __init__(
        self,
        scope: constructs,
        id: str,
        model_endpoint,
        vpc,
        **kwargs,
    ):

        super().__init__(scope, id, **kwargs)

        stage_name = Stage.of(self).stage_name.lower()

        # load constants required for each stage
        try:
            stage_constants = importlib.import_module(f"cdk_pipelines.config.{stage_name}.constants")
        except Exception:
            stage_constants = importlib.import_module(
                "cdk_pipelines.config.dev.constants"
            )  # use default configs which are inf-dev configs in this case

        # create lambda layer for aws powertools package
        aws_lambda_powertools_lambda_layer = PythonLayerVersion(
            self,
            "AWSLambdaPowerTools",
            entry=f"{LAMBDA_FUNCTION_ENTRY}/layers/aws_lambda_powertools",
            compatible_runtimes=[
                lambda_.Runtime.PYTHON_3_7,
                lambda_.Runtime.PYTHON_3_8,
            ],
        )

        # subnets resources should use
        subnets = [
            ec2.Subnet.from_subnet_id(self, f"SUBNET-{subnet_id}", subnet_id)
            for subnet_id in stage_constants.APP_SUBNETS
        ]

        # account base security group
        base_security_group = ec2.SecurityGroup.from_security_group_id(
            self, "BaseSG", security_group_id=stage_constants.BASE_SECURITY_GROUP
        )

        # lambda function for running inference for delivery risk ml models
        inference_api_lambda_function = PythonFunction(
            self,
            "APIFunction",
            entry=f"{LAMBDA_FUNCTION_ENTRY}/inference/api",
            description="run inference endpoint for delivery risk data",
            environment={
                "POWERTOOLS_LOGGER_SAMPLE_RATE": "1",
                "ENDPOINT_NAME": model_endpoint.endpoint_name,
            },
            layers=[
                aws_lambda_powertools_lambda_layer,
            ],
            runtime=lambda_.Runtime.PYTHON_3_7,
            function_name=f"{APP_PREFIX}-{stage_name}-inference-api",
            timeout=Duration.seconds(stage_constants.DEFAULT_TIMEOUT),
            memory_size=stage_constants.INFERENCE_MEMORY_SIZE,
            vpc=vpc,
            security_groups=[base_security_group],
            vpc_subnets=ec2.SubnetSelection(subnets=subnets),
            reserved_concurrent_executions=100,
        )

        inference_api_lambda_function.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole")
        )

        inference_api_lambda_function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                effect=iam.Effect.ALLOW,
                resources=[
                    f"arn:aws:logs:*:{Aws.ACCOUNT_ID}:log-group:*",
                    f"arn:aws:logs:*:{Aws.ACCOUNT_ID}:log-group:*:log-stream:*",
                ],
            )
        )

        inference_api_lambda_function.role.add_to_policy(
            iam.PolicyStatement(
                actions=["sagemaker:InvokeEndpoint"],
                effect=iam.Effect.ALLOW,
                resources=[f"arn:aws:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:endpoint/{MODEL_PACKAGE_GROUP_NAME}*"],
            )
        )

        # api gateway log group setup for inference
        kms_key = kms.Key(
            self,
            "KMSKey",
            enable_key_rotation=True,
            description="key used for encryption of data for api gateway logs",
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["kms:*"],
                        effect=iam.Effect.ALLOW,
                        resources=["*"],
                        principals=[iam.AccountRootPrincipal()],
                    ),
                    iam.PolicyStatement(
                        actions=["kms:*"],
                        effect=iam.Effect.ALLOW,
                        resources=["*"],
                        principals=[iam.ServicePrincipal(f"logs.{Aws.REGION}.amazonaws.com")],
                    ),
                ]
            ),
        )

        prd_log_group = logs.LogGroup(self, "PrdLogs", encryption_key=kms_key)

        # api gateway setup for inference
        api = api_gateway.LambdaRestApi(
            self,
            "InferenceAPI",
            handler=inference_api_lambda_function,
            proxy=False,
            deploy_options=api_gateway.StageOptions(
                access_log_destination=api_gateway.LogGroupLogDestination(prd_log_group),
            ),
        )

        inference_resource = api.root.add_resource("inference")
        inference_resource.add_method(
            "POST", api_key_required=True, authorization_type=api_gateway.AuthorizationType.IAM
        )

        plan = api.add_usage_plan(
            "UsagePlan", name="Easy", throttle=api_gateway.ThrottleSettings(rate_limit=10, burst_limit=2)
        )

        plan.add_api_stage(
            stage=api.deployment_stage,
        )

        key = api.add_api_key("ApiKey")
        plan.add_api_key(key)
