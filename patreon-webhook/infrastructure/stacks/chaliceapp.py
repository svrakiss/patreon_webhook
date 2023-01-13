import os

from aws_cdk import aws_dynamodb as dynamodb
import aws_cdk.aws_ssm as ssm

try:
    from aws_cdk import core as cdk
except ImportError:
    import aws_cdk as cdk

from chalice.cdk import Chalice


RUNTIME_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), os.pardir, 'runtime')


class ChaliceApp(cdk.Stack):

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.dynamodb_table = self._create_ddb_table()
        self.chalice = Chalice(
            self, 'ChaliceApp', source_dir=RUNTIME_SOURCE_DIR,
            stage_config={
                'environment_variables': {
                    'APP_TABLE_NAME': self.dynamodb_table.table_name
                }
            }
        )
        self.dynamodb_table.grant_read_write_data(
            self.chalice.get_role('DefaultRole')
        )

    def _create_ddb_table(self):
        tableName = ssm.StringParameter.value_for_string_parameter(self,parameter_name="/config/ValidatorMS-production/spring.cloud.aws.dynamodb.tableName")
        dynamodb_table = dynamodb.Table.from_table_name(self,"chaliceTable",table_name=tableName)
        cdk.CfnOutput(self, 'AppTableName',
                      value=dynamodb_table.table_name)
        return dynamodb_table
