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

patch_all()


app = Chalice(app_name='patreon-webhook-webhook')
dynamodb = boto3.resource('dynamodb')
dynamodb_table = dynamodb.Table(os.environ.get('APP_TABLE_NAME', ''))
app.debug = True
@app.on_dynamodb_record(os.environ.get('APP_STREAM_ARN'),name='stateChange')
def find_all(event: DynamoDBEvent):
    for r in event:
        if r.event_name != "MODIFY" or r.keys.get('SortKey') != {"S":"INFO"}: # put this in the filter criteria
            app.log.debug("Shouldn't be here")
            app.log.debug(f"Image {r.new_image}")
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
@app.on_dynamodb_record(os.environ.get('APP_STREAM_ARN'),name='tierChange')
def change_tier(event: DynamoDBEvent):
    for r in event:
        if r.event_name != "MODIFY" or r.keys.get('SortKey') != {"S":"INFO"}: # put this in the filter criteria
            app.log.debug("Shouldn't be here")
            app.log.debug(f"Image {r.new_image}")
            continue
        result = decide(r)
        if result == "approve": # calculate PatStats
            app.log.debug(f"Approve {r.new_image}")
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


def decide(resp:DynamoDBRecord):
    if resp.old_image.get('Status') == None:
        if resp.new_image.get('Status') == {'S':'active_patron'}:
            return "approve"
        return "nothing"
    if resp.old_image.get('Status')== {'S':'active_patron'}:
        if resp.new_image.get('Status')!= {'S': 'active_patron'}:
            return "disapprove"
        return "nothing"
    if resp.new_image.get('Status') == {'S':'active_patron'}:
        return "approve"
    return "nothing"
class tier_enum(enum.Enum):
    TIER_1 = (1, 'Supreme Kimochi Counsellor','SKC')
    TIER_2 = (2,'Envoy of Lewdness','EoL')
    TIER_3 = (3, 'Minister of Joy','MoJ')
    def __init__(self,order:int,name:str,code:str) -> None:
        self._order=order
        self._name=name
        self.code =code
    @property
    def order(self):
        return self._order
    @property
    def name(self):
        return self._name
    def __lt__(self,other):
        return self._order < other._order
    @classmethod
    def get(cls,name,default=None):
        try:
            return cls[name]
        except KeyError:
            return default

def get_stat(resp:DynamoDBRecord):
    def sub_fun(respy:str)->str:
        if respy is None:
            return "YEP"
        operations :list[Callable]= [
             lambda x: tier_enum.get(x,tier_enum.TIER_1),
             lambda x: x.code
        ]
        return  reduce(lambda x, f: f(x), operations,respy)
    try:    
        return sub_fun(resp.new_image.get('HTier'))
    except:
        app.log.error(traceback.format_exc())
        return "YEP"