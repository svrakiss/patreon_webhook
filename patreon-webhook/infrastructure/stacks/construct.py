import json,yaml
import os
import uuid
from typing import List, Dict, Optional, Any
from aws_cdk import (
    aws_s3_assets as assets,
    cloudformation_include,
    aws_iam as iam,
    aws_lambda as lambda_,
)
from stacks import api

from chalice.cdk import Chalice
from constructs import Construct
class MergeableChalice(Chalice):
    def __init__(self, scope: Construct, id: str, source_dir: str, stage_config: Optional[Dict[str, Any]] = None, preserve_logical_ids: bool = True,merge_template:str=None, **kwargs: Dict[str, Any]) -> None:
         # type: (...) -> None
        super(Chalice,self).__init__(scope, id, **kwargs)
        #: (:class:`str`) Path to Chalice application source code.
        self.source_dir = os.path.abspath(source_dir)

        #: (:class:`str`) Chalice stage name.
        #: It is automatically assigned the encompassing CDK ``scope``'s name.
        self.stage_name = scope.to_string()

        #: (:class:`dict`) Chalice stage configuration.
        #: The object has the same structure as Chalice JSON stage
        #: configuration.
        self.stage_config = stage_config
        self.merge_template=merge_template
        self.file_format = "yml"
        chalice_out_dir = os.path.join(os.getcwd(), 'chalice.out')
        package_id = uuid.uuid4().hex
        self._sam_package_dir = os.path.join(chalice_out_dir, package_id)

        self._package_app()
        sam_template_filename = self._generate_sam_template_with_assets(
            chalice_out_dir, package_id)

        #: (:class:`aws_cdk.cloudformation_include.CfnInclude`) AWS SAM
        #: template updated with AWS CDK values where applicable. Can be
        #: used to reference, access, and customize resources generated
        #: by `chalice package` commandas CDK native objects.
        self.sam_template = cloudformation_include.CfnInclude(
            self, 'ChaliceApp', template_file=sam_template_filename,
            preserve_logical_ids=preserve_logical_ids)
        self._function_cache = {}  # type: Dict[str, lambda_.IFunction]
        self._role_cache = {}  # type: Dict[str, iam.IRole]
    def _package_app(self):
        # type: () -> None
        api.package_app(
            project_dir=self.source_dir,
            output_dir=self._sam_package_dir,
            stage=self.stage_name,
            chalice_config=self.stage_config,
            merge_template=self.merge_template
        )

    def _generate_sam_template_with_assets(self, chalice_out_dir, package_id):
        # type: (str, str) -> str
        
        deployment_zip_path = os.path.join(
            self._sam_package_dir, 'deployment.zip')
        sam_deployment_asset = assets.Asset(
            self, 'ChaliceAppCode', path=deployment_zip_path)
        sam_template_path = os.path.join(self._sam_package_dir, 'sam.yaml')
        sam_template_with_assets_path = os.path.join(
            chalice_out_dir, '%s.sam_with_assets.yaml' % package_id)

        with open(sam_template_path,"r") as sam_template_file:
            sam_template = yaml.safe_load(sam_template_file)
            for function in self._filter_resources(
                    sam_template, 'AWS::Serverless::Function'):
                function['Properties']['CodeUri'] = {
                    'Bucket': sam_deployment_asset.s3_bucket_name,
                    'Key': sam_deployment_asset.s3_object_key
                }
            managed_layers = self._filter_resources(
                sam_template, 'AWS::Serverless::LayerVersion')
            if len(managed_layers) == 1:
                layer_filename = os.path.join(
                    self._sam_package_dir, 'layer-deployment.zip')
                layer_asset = assets.Asset(
                    self, 'ChaliceManagedLayer', path=layer_filename)
                managed_layers[0]['Properties']['ContentUri'] = {
                    'Bucket': layer_asset.s3_bucket_name,
                    'Key': layer_asset.s3_object_key
                }
        with open(sam_template_with_assets_path, 'w') as f:
            f.write(yaml.dump(sam_template, indent=2))
        return sam_template_with_assets_path
