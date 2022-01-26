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

import importlib
from aws_cdk import (
    Aws,
    Fn,
    Stack,
    Stage,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_sagemaker as sagemaker,
)
import constructs

from cdk_pipelines.code.scripts.sm_model import get_approved_package

from cdk_pipelines.config.constants import (
    APP_PREFIX,
    DEV_ACCOUNT,
    MODEL_PACKAGE_GROUP_NAME,
)

from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from yamldataclassconfig import create_file_path_field
from cdk_pipelines.config.config_mux import StageYamlDataClassConfig


@dataclass
class EndpointConfigProductionVariant(StageYamlDataClassConfig):
    """
    Endpoint Config Production Variant Dataclass
    a dataclass to handle mapping yml file configs to python class for endpoint configs
    """

    initial_instance_count: float = 1
    initial_variant_weight: float = 1
    instance_type: str = "ml.m5.2xlarge"
    variant_name: str = "AllTraffic"

    FILE_PATH: Path = create_file_path_field("endpoint-config.yml", path_is_absolute=True)

    def get_endpoint_config_production_variant(self, model_name):
        """
        Function to handle creation of cdk glue job. It use the class fields for the job parameters.

        Parameters:
            model_name: name of the sagemaker model resource the sagemaker endpoint would use

        Returns:
            CfnEndpointConfig: CDK SageMaker CFN Endpoint Config resource
        """

        production_variant = sagemaker.CfnEndpointConfig.ProductionVariantProperty(
            initial_instance_count=self.initial_instance_count,
            initial_variant_weight=self.initial_variant_weight,
            instance_type=self.instance_type,
            variant_name=self.variant_name,
            model_name=model_name,
        )

        return production_variant


class DeployModelStack(Stack):
    """
    Deploy Model Stack
    Deploy Model stack which provisions SageMaker Model Endpoint resources.
    """

    def __init__(
        self,
        scope: constructs,
        id: str,
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

        # iam role that would be used by the model endpoint to run the inference
        model_execution_policy = iam.ManagedPolicy(
            self,
            "ModelExecutionPolicy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["s3:*"],
                        effect=iam.Effect.ALLOW,
                        resources=[
                            f"arn:aws:s3:::{APP_PREFIX}*",
                        ],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "kms:Encrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*",
                            "kms:Decrypt",
                            "kms:DescribeKey",
                        ],
                        effect=iam.Effect.ALLOW,
                        resources=[f"arn:aws:kms:{Aws.REGION}:{DEV_ACCOUNT}:key/*"],
                    ),
                    iam.PolicyStatement(
                        actions=["ecr:*"],
                        effect=iam.Effect.ALLOW,
                        resources=[
                            f"arn:aws:ecr:{Aws.REGION}:{DEV_ACCOUNT}:repository/{APP_PREFIX}*",
                        ],
                    ),
                ]
            ),
        )

        model_execution_role = iam.Role(
            self,
            "ModelExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                model_execution_policy,
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
            ],
        )

        # setup timestamp to be used to trigger the custom resource update event to retrieve latest approved model and to be used with model and endpoint config resources' names
        now = datetime.now().replace(tzinfo=timezone.utc)

        timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")

        # get latest approved model package from the model registry (only from a specific model package group)
        latest_approved_model_package = get_approved_package()
        # latest_approved_model_package ="1"

        # vpc resource to be used for the endpoint and lambda vpc configs
        self.vpc = ec2.Vpc.from_vpc_attributes(
            self, "VPC", vpc_id=stage_constants.VPC_ID, availability_zones=Fn.get_azs()
        )

        # subnets resources should use
        subnets = [
            ec2.Subnet.from_subnet_id(self, f"SUBNET-{subnet_id}", subnet_id)
            for subnet_id in stage_constants.APP_SUBNETS
        ]

        # security group for the model endpoint
        # account base security group
        base_security_group = ec2.SecurityGroup.from_security_group_id(
            self, "BaseSG", security_group_id=stage_constants.BASE_SECURITY_GROUP
        )

        # Sagemaker Model
        model_name = f"{MODEL_PACKAGE_GROUP_NAME}-{stage_name}-{timestamp}"

        model = sagemaker.CfnModel(
            self,
            "Model",
            execution_role_arn=model_execution_role.role_arn,
            model_name=model_name,
            containers=[
                sagemaker.CfnModel.ContainerDefinitionProperty(model_package_name=latest_approved_model_package)
            ],
            vpc_config=sagemaker.CfnModel.VpcConfigProperty(
                security_group_ids=[base_security_group.security_group_id],
                subnets=[subnet.subnet_id for subnet in subnets],
            ),
        )

        # Sagemaker Endpoint Config
        endpoint_config_name = f"{MODEL_PACKAGE_GROUP_NAME}-{stage_name}-endpointConfig-{timestamp}"

        endpoint_config_production_variant = EndpointConfigProductionVariant()

        endpoint_config_production_variant.load_for_stage(self)

        endpoint_config = sagemaker.CfnEndpointConfig(
            self,
            "EndpointConfig",
            endpoint_config_name=endpoint_config_name,
            production_variants=[
                endpoint_config_production_variant.get_endpoint_config_production_variant(model.model_name)
            ],
        )

        endpoint_config.add_depends_on(model)

        # Sagemaker Endpoint
        endpoint_name = f"{MODEL_PACKAGE_GROUP_NAME}-{stage_name}-endpoint"

        endpoint = sagemaker.CfnEndpoint(
            self,
            "Endpoint",
            endpoint_config_name=endpoint_config.endpoint_config_name,
            endpoint_name=endpoint_name,
        )

        endpoint.add_depends_on(endpoint_config)

        self.endpoint = endpoint
