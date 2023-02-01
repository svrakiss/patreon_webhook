import os

from aws_cdk import aws_dynamodb as dynamodb
import aws_cdk.aws_ssm as ssm
try:
    from aws_cdk import core as cdk
except ImportError:
    import aws_cdk as cdk

from chalice.cdk import Chalice
import aws_cdk.aws_iam  as iam

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.dynamodb_table = self._create_ddb_table()
        role = iam.Role(self,"DeafRole",assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"));
        self.chalice = Chalice(
            self, 'ChaliceApp', source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                'environment_variables': {
                    'APP_TABLE_NAME': self.dynamodb_table.table_name
                },
                'iam_role_arn':role.role_arn,
                'manage_iam_role':False
            },

        )
        rest_api = self.chalice.sam_template.get_resource('RestAPI')
        rest_api.tracing_enabled=True
        api_handler = self.chalice.sam_template.get_resource('APIHandler')
        api_handler.tracing = 'Active'
        self.dynamodb_table.grant_read_write_data(
            role
        )
       
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess")
        )
        role.attach_inline_policy(
            iam.Policy(self,'indexPolicy',
            statements=[iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[self.dynamodb_table.table_arn+'/index/*']
            )])
        )
        role.attach_inline_policy(
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
        

    def _create_ddb_table(self):
        tableName = ssm.StringParameter.value_for_string_parameter(self,parameter_name="/config/ValidatorMS-production/spring.cloud.aws.dynamodb.tableName")
        dynamodb_table = dynamodb.Table.from_table_name(self,"chaliceTable",table_name=tableName)
        cdk.CfnOutput(self, 'AppTableName',
                      value=dynamodb_table.table_name)
        return dynamodb_table
