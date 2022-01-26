# CDK Pipelines
This repository contains the resources that are required to deploy the ML model to multiple accounts. It includes the lambda required to run inference. This repository can be exteneded to be used with other ML Models.

## Installation
### Prerequisites
This is an AWS CDK project written in Python 3.8. Here's what you need to have on your workstation before you can deploy this project. It is preferred to use a linux OS to be able to run all cli commands and avoid path issues.

* [Node.js](https://nodejs.org/)
* [Python3.8](https://www.python.org/downloads/release/python-380/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
* [AWS CDK](https://aws.amazon.com/cdk/)
* [AWS CLI](https://aws.amazon.com/cli/)

**NOTES** The pipelines in this repository are setup to monitor a codecommit repository if you are using other sources for your repository you will need to modify the connection to the appropriate repository. Make sure the pipelines also point to your targeted branch.

### Setup
```
.
├── .gitignore
├── .pre-commit-config.yaml
├── LICENSE.txt
├── Makefile
├── README.md
├── app.py
├── cdk.json
├── cdk_pipelines
│   ├── __init__.py
│   ├── code
│   │   └── functions                       <--- lambda functions and layers
│   │       ├── inference
│   │       └── layers
│   ├── config
│   │   ├── config_mux.py
│   │   ├── constants.py                    <--- global configs regardless of account
│   │   └── inf-dev                         <--- configs for dev account (default configs if not present in other config folders)
│   │   │   ├── constants.py
│   │   │   └── endpoint-config.yml
│   │   └── inf-prod                        <--- configs for prod account
│   │       ├── constants.py
│   │       └── endpoint-config.yml
│   ├── deploy_model_pipeline_stack.py      <--- CICD with code pipeline setup for the repo
│   ├── deploy_model_stack.py               <--- Sagemaker Model Endpoint deployment
│   └── inference_stack.py                  <--- Inference lambda and code for pilot
└──requirements.txt                        <--- cdk packages used in the stacks (must be installed)

```

### Deployment Guide
*make sure you are using the right role (aws profile) with enough permission to deploy to cloudformation*
1. Change directory to `cdk-pipelines`'s root
    ```bash
    cd cdk-pipelines
    ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Bootstrap your deployment target accounts. For each target account, run:
    ```bash
    cdk bootstrap aws://<target account id>/<target region> --profile <target account profile>
    ```
   The bootstrap stack needs only to be deployed for the first time. Once deployed, the bootstrap will be updated as
   part of the pipeline's regular execution. You only need to deploy bootstrap into new target accounts you plan to
   add to the pipeline. (in case you get an error regarding CDK version not matching run the bootstrap command again 
   after you have locally updated your cdk)
4. Deploy the pipeline in your tooling account (happens locally once)
    ```bash
    # builds the pipeline stack and install all assets
    cdk synth

    # deploy stack to target account
    cdk deploy
    ```
5. the pipeline will now handle all deployments for the other stacks based on the updates to the main branch

**NOTE** The pipeline also gets triggered on model updates which are driven through the even bridge of model approved event in Amazon SageMaker Model Registry.

### Local Deployment Guide
It is possible to deploy a specific stage from the pipeline stack (in `deploy_model_pipeline_stack.py` refer to classes inherting `core.stage` class from `aws_cdk.core`). The same is possible to a singular stack (follow the same deployment steps as the pipeline stack).

*make sure you are using the right role (aws profile) with enough permission to deploy to cloudformation*
1. Add a custom id to the target stage in `app.py`
   ```python
   # Personal Stacks for testing locally, comment out when committing to repository

    if not os.getenv("CODEBUILD_BUILD_ARN"):
        ModelStage(
            app,
            "Personal",  ## change this to another stack name when doing local tests
            env=deployment_env,
        )
   ```
2. Deploy the stage
    ```bash
    # builds the pipeline stack and install all assets
    cdk synth

    # deploy stage to target account (make it match your stack name)
    cdk --app ./cdk.out/assembly-Personal deploy --all
    ```
    as a stage could include a combination of stacks `--all` flag is included with the `deploy` command



### Clean Up Local Deployment
once you are done with testing the new feature that was deployed locally, run the following to clean-up the environment:
```bash
# destroy stage to target account (make it match your stack name)
cdk --app ./cdk.out/assembly-Personal destroy --all
```
This command could fail in the following cases:
- **S3 bucket not empty**
  If you get this error just simply go to the console and empty the S3 bucket that caused the error and run the destroy command again.
- **Resource being used by another resource**
  This error is harder to track and would require some effort to trace where is the resource that we want to delete is being used and severe that dependency before running the destroy command again.

**NOTE** You should just really follow CloudFormation error messages and debug from there as they would include details about which resource is causing the error and in some occation information into what needs to happen in order to resolve it.

### Misc pre-commit commands
* make sure to run `pre-commit install` to properly setup your git commits, this will allow your code to be formatted and checked of any errors/conflicts before committing

### Troubleshooting
- **CDK version X instead of Y** -
  This error relates to a new update to cdk so run `npm install -g aws-cdk` again to update your cdk to the latest version and then run the deployment step again for each account that your stacks are deployed.
- **`cdk synth` not running** -
  One of the following would solve the problem:
  - Docker is having an issue so restart your docker deamon
  - Refresh your awscli credentials
  - Clear all cached cdk outputs by running `make clean`

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

## Authors
- Fatema Alkhanaizi (https://github.com/Fatema)
- Francesco Vito Lorenzo (https://github.com/iPhra)
- Laurens Ten Cate (https://github.com/Laurenstc)