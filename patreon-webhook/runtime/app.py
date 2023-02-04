import os
import boto3
from chalice import Chalice, Response
from patreon.jsonapi.parser import JSONAPIParser, JSONAPIResource
import hmac
from datetime import datetime
import boto3.dynamodb.types
from boto3.dynamodb.conditions import Key, Attr
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from chalice.app import DynamoDBEvent,DynamoDBRecord
patch_all()

app = Chalice(app_name='patreon-webhook-webhook')
dynamodb = boto3.resource('dynamodb')
dynamodb_table = dynamodb.Table(os.environ.get('APP_TABLE_NAME', ''))
app.debug = True
@app.on_dynamodb_record(os.environ.get('APP_STREAM_ARN'),name='stateChange')
def find_all(event: DynamoDBEvent):
    for r in event:
        if r.event_name != "MODIFY" or r.keys.get('SortKey') != {"S":"INFO"}: # put this in the filter criteria
            continue
        result = decide(r)
        if result == "disapprove" or result == "approve":
            app.log.debug(f"New {r.new_image}")
            # dynamodb_table.query(
                # KeyConditionExpression=Key('PartKey').eq(r.keys.get('PartKey').get("S")).__and__(Key('SortKey').eq('INFO').__invert__())
            # )

def decide(resp:DynamoDBRecord):
    if resp.old_image.get('Status').get('S') == 'active_patron':
        if resp.new_image.get('Status').get('S') != 'active_patron':
            return "disapprove"
        return "nothing"
    if resp.new_image.get('Status').get('S') == 'active_patron':
        return "approve"
    return "nothing"