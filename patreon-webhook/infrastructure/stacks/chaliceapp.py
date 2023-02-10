import os
import json
from aws_cdk import aws_dynamodb as dynamodb
import aws_cdk.aws_ssm as ssm
import aws_cdk.aws_lambda as _lambda
from aws_cdk.aws_lambda import CfnEventSourceMapping
from aws_cdk.aws_sam import CfnFunction
from stacks.construct import MergeableChalice
try:
    from aws_cdk import core as cdk
except ImportError:
    import aws_cdk as cdk

from chalice.cdk import Chalice
import aws_cdk.aws_iam as iam

RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.dynamodb_table = self._create_ddb_table()
        role = iam.Role(self, "DeafRole", assumed_by=iam.ServicePrincipal(
            "lambda.amazonaws.com"))
        self.make_template()

        self.chalice = MergeableChalice(
            self, 'ChaliceApp', source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                'environment_variables': {
                    'APP_TABLE_NAME': self.dynamodb_table.table_name,
                    'APP_STREAM_ARN': self.dynamodb_table.table_stream_arn
                },
                'iam_role_arn': role.role_arn,
                'manage_iam_role': False,
                'xray': True
            }, merge_template='extras.yml'

        )
        self.dynamodb_table.grant_read_write_data(
            role
        )
        self.dynamodb_table.grant_stream_read(role)
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AWSXRayDaemonWriteAccess")
        )
        role.attach_inline_policy(
            iam.Policy(self, 'indexPolicy',
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

    def filters(self):
        filters = {"Filters": [
            # pattern for approval state change
            {
                "Pattern": json.dumps(
                    {"dynamodb":
                     {"Keys": {
                         "SortKey": {"S": ["INFO"]}
                     }, "NewImage":
                         {"Status": {"S": ["active_patron"]}},
                         "OldImage":
                             {"Status":
                              {"S":
                               [{"anything-but": ["active_patron"]}
                                ]}
                              }
                     }
                     }
                )
            },
            {
                "Pattern": json.dumps(
                    {"dynamodb":
                     {"Keys": {
                         "SortKey": {"S": ["INFO"]}
                     },
                         "NewImage":
                         {
                         "Status": {"S": ["active_patron"]}
                     },
                         "OldImage":
                         {
                         "Status": {"S": [None]}
                     }
                     }}
                )
            },
            {
                "Pattern": json.dumps(
                    {"dynamodb":
                     {"Keys": {
                         "SortKey": {"S": ["INFO"]}
                     },
                         "NewImage":
                         {
                         "Status": {"S": ["active_patron"]}
                     },
                         "OldImage":
                         {
                         "Status": {"S": [{"exists": False}]}
                     }
                     }}
                )
            },
            # pattern for disapproval state change
            {
                "Pattern": json.dumps(
                    {"dynamodb":
                     {"Keys": {
                         "SortKey": {"S": ["INFO"]}
                     }, "OldImage":
                         {"Status": {"S": ["active_patron"]}
                          },
                         "NewImage":{
                        "Status": {"S": [{"anything-but": ["active_patron"]}]}
                     }
                     }
                     }
                )
            }
        ]
        }
        return {"Resources":
                {"StateChange":
                 {"Properties":
                  {"Events":
                   {"StateChangeDynamodbEventSource":
                    {"Properties":
                     {"FilterCriteria": filters}
                     }}
                   }}
                 }}

    def make_template(self):
        import yaml
        # print(self.filters())
        with open('extras.yml', 'w') as outfile:
            return yaml.dump(self.filters(), outfile, allow_unicode=True)

    def _create_ddb_table(self):
        tableName = ssm.StringParameter.value_for_string_parameter(
            self, parameter_name="/config/ValidatorMS-production/spring.cloud.aws.dynamodb.tableName")
        stream_arn = ssm.StringParameter.value_for_string_parameter(
            self, parameter_name="/config/ValidatorMS-production/TableStreamArn")
        dynamodb_table = dynamodb.Table.from_table_attributes(
            self, "chaliceTable", table_name=tableName, table_stream_arn=stream_arn)
        cdk.CfnOutput(self, 'AppTableName',
                      value=dynamodb_table.table_name)
        return dynamodb_table
