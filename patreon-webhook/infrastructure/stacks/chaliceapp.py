import os

from aws_cdk import aws_dynamodb as dynamodb
import aws_cdk.aws_ssm as ssm

try:
    from aws_cdk import core as cdk
except ImportError:
    import aws_cdk as cdk

from chalice.cdk import Chalice
import aws_cdk.aws_iam  as iam
import json
RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(cdk.Stack):
# Can you create 2 chalice functions using the aws cdk using the same resources except for a single identifier? To clarify, I'm using the chalice-cdk integration and I want to deploy 2 slightly different versions of the same function but use a shared 
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.dynamodb_table = self._create_ddb_table()
        self.role = iam.Role(self,"DeafRole",assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"));
        variations = {"":"","1":"/1"}
        secret_name_map = { k:f'/config/patreon-webhook/secret{item}' for k,item   in variations.items()}
        self.chalice = Chalice(
            self, 'ChaliceApp', source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                'environment_variables': {
                    'APP_TABLE_NAME': self.dynamodb_table.table_name,
                    "WEBHOOK_SECRET":json.dumps(secret_name_map)
                },
                'iam_role_arn':self.role.role_arn,
                'manage_iam_role':False,
                "automatic_layer":True,            
            },

        )
        rest_api = self.chalice.sam_template.get_resource('RestAPI')
        rest_api.tracing_enabled=True
        api_handler = self.chalice.sam_template.get_resource('APIHandler')
        api_handler.tracing = 'Active'
        self.dynamodb_table.grant_read_write_data(
            self.role
        )
       
        self.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess")
        )
        self.role.attach_inline_policy(
            iam.Policy(self,'indexPolicy',
            statements=[iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[self.dynamodb_table.table_arn+'/index/*']
            )])
        )
        self.role.attach_inline_policy(
            iam.Policy(self,
           "logsPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"],
                    resources=["arn:*:logs:*:*:*"],
                    effect=iam.Effect.ALLOW
                )
            ])
        )
        for i,webhook_secret in enumerate(secret_name_map.values()):
            self.grant_secret_read(webhook_secret,i)

    def grant_secret_read(self, webhook_secret,index:int):
        secret = ssm.StringParameter.from_secure_string_parameter_attributes(self, f"webhookSecret {index}",parameter_name=webhook_secret)
        secret.grant_read(self.role)


    def _create_ddb_table(self):
        tableName = ssm.StringParameter.value_for_string_parameter(self,parameter_name="/config/ValidatorMS-production/spring.cloud.aws.dynamodb.tableName")
        dynamodb_table = dynamodb.Table.from_table_name(self,"chaliceTable",table_name=tableName)
        cdk.CfnOutput(self, 'AppTableName',
                      value=dynamodb_table.table_name)
        return dynamodb_table
