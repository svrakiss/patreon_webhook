import enum
from functools import reduce
import os
import traceback
from typing import Callable, TypeVar
import boto3
from chalice import Chalice, Response
from patreon.jsonapi.parser import JSONAPIParser, JSONAPIResource
from chalicelib.table import Patron 
from datetime import datetime
import boto3.dynamodb.types
from boto3.dynamodb.conditions import Key, Attr
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from chalice.app import DynamoDBEvent,DynamoDBRecord
from pat_tools.utils import tier_enum
patch_all()


app = Chalice(app_name='patreon-webhook-webhook')
dynamodb = boto3.resource('dynamodb')
dynamodb_table = dynamodb.Table(os.environ.get('APP_TABLE_NAME', ''))
app.debug = True
@app.on_dynamodb_record(os.environ.get('APP_STREAM_ARN'),name='stateChange')
def find_all(event: DynamoDBEvent):
    """This should be disabled, if it is actually possible to retain an entitlement as a non-patron"""
    for r in event:
        if r.event_name != "MODIFY" or r.keys.get('SortKey') != {"S":"INFO"}: # put this in the filter criteria
            app.log.debug("Shouldn't be here")
            app.log.debug(f"Image {r.new_image}")
            app.log.debug(f"Event {r._event_dict}")
            continue
        result = decide(r)
        if result == "approve": # calculate PatStats
            app.log.debug(f"Approve {r.new_image}")
            app.log.debug(f'Approve old: {r.old_image}')
            to_change_actually =Patron.query(r.keys.get('PartKey').get('S'),Patron.sort_key.startswith("CHANNEL"))
            stat=get_stat(r)
            for i in to_change_actually:
                i.update(
                    [
                        Patron.pat_stats.set(stat)
                    ]
                )
                app.log.debug( i.attribute_values)

        elif result == "disapprove":
            app.log.debug(f"Disapprove {r.new_image}")

            to_change_actually =Patron.query(r.keys.get('PartKey').get('S'),Patron.sort_key.startswith("CHANNEL"))
            for i in to_change_actually:
                i.update(
                    [
                        Patron.pat_stats.remove()
                    ]
                )
            # remove PatStats
        elif result == "nothing":
            app.log.debug("shouldn't be here")
            app.log.debug(f"Image {r.new_image}")
            app.log.debug(f"Event {r._event_dict}")

@app.on_dynamodb_record(os.environ.get('APP_STREAM_ARN'),name='tierChange')
def change_tier(event: DynamoDBEvent):
    for r in event:
        result = decide(r)
        if result == "approve": # calculate PatStats
            app.log.debug(f"Approve {r.new_image}")
            to_change_actually =get_my_submissions(r)
            stat=get_stat(r)
            for i in to_change_actually:
                i.update(
                    [
                        Patron.pat_stats.set(stat)
                    ]
                )
                app.log.debug( i.attribute_values)
        elif result == "disapprove":
            """Remove the pat_stats from the submissions"""
            to_change_actually = get_my_submissions(r)
            for i in to_change_actually:
                i.update( actions=[Patron.pat_stats.remove()])
                app.log.debug( i.attribute_values)

        elif result == "nothing":
            app.log.debug("shouldn't be here")
            app.log.debug(f"Image {r.new_image}")
            app.log.debug(f"event {r._event_dict}")

def get_my_submissions(record:DynamoDBRecord):
    """Get submissions for the patron"""
    return Patron.query(record.keys.get('PartKey').get('S'),Patron.sort_key.startswith("CHANNEL"))

def decide(resp:DynamoDBRecord):
    if resp.old_image.get('HTier') == None:
        if resp.new_image.get('HTier') != None:
            return "approve"
        return "nothing"
    elif resp.old_image.get('HTier')!= resp.new_image.get('HTier'):
        return "approve"
    elif resp.new_image.get("HTier") == None:
        return "disapprove"
    return "nothing" 

def get_stat(resp:DynamoDBRecord):
    def sub_fun(respy:dict[str,str])->str:
        if respy is None:
            return "YEP"
        operations :list[Callable]= [
            lambda x: x.get("S"),
             lambda x: tier_enum.get(x,tier_enum.TIER_1),
             lambda x: x.code
        ]
        return  reduce(lambda x, f: f(x), operations,respy)
    try:    
        return sub_fun(resp.new_image.get('HTier'))
    except:
        app.log.error(traceback.format_exc())
        return "YEP"