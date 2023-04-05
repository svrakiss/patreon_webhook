import enum
from functools import reduce
import os
import traceback
from typing import Callable, TypeVar
import boto3
from chalice import Chalice, Response
from patreon.jsonapi.parser import JSONAPIParser, JSONAPIResource
import hmac
from datetime import datetime,timezone
from pynamodb.settings import default_settings_dict
import boto3.dynamodb.types
from boto3.dynamodb.conditions import Key, Attr
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from chalicelib.table import CharacterMeta, Patron
from chalicelib.custom import AWSISODateTimeAttribute
from pat_tools.utils import tier_enum
import logging
patch_all()
logging.basicConfig()
_log = logging.getLogger()
app = Chalice(app_name='patreon-connection')
dynamodb = boto3.resource('dynamodb')
dynamodb_table = dynamodb.Table(os.environ.get('APP_TABLE_NAME', ''))
app.debug=True
@app.route('/character',methods = ['POST','PUT'])
def add_character():
    request = app.current_request.json_body
    if request.get('discordId') !=None:
        response =find_by_discordId_pynamo(request)
        if len(response) == 0:
            return Response(body={'message': 'DiscordId did not refer to a patron'}, status_code=400, headers={'Content-Type':'application/json'})
    elif request.get('userId') != None:
        response = find_by_userId(request)
        if len(response)==0:
            return Response(body={'message': 'UserId did not refer to a patron'}, status_code=400, headers={'Content-Type':'application/json'})

    item_val={"PartKey": response[0].part_key, "SortKey": request.get('sortKey'), 'CharacterName':request.get('characterName')}
    item=Patron(response[0].part_key,request.get('sortKey'))
    item.character_name= request.get('characterName')
    if(request.get('category') is not None):
        item_val['Category']= request.get('category')
        item.category = request.get('category')
    if(request.get('creationDate') is not None):
        item.creation_date =datetime.fromisoformat(request.get('creationDate')) # so that it will be validated
        item_val['CreationDate'] =item.creation_date.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace("+00:00", "Z")
    # the problem with boto is it doesn't let you upsert Map Attributes
    if(request.get('meta') is not None):
        item_val['CharacterMeta'] = {}
        if request.get('meta').get('artist') !=None:
            item_val['CharacterMeta']['Artist']=request.get('meta').get('artist')
        if request.get('meta').get('source') !=None:
            item_val['CharacterMeta']['Source']=request.get('meta').get('source')
        if request.get('meta').get('comments') !=None:
            item_val['CharacterMeta']['Comments']=request.get('meta').get('comments')
        if request.get('meta').get('image')!=None:
            item_val['CharacterMeta']['Image']=request.get('meta').get('image')
        if request.get('meta').get('status') !=None:
            item_val['CharacterMeta']['Status']=request.get('meta').get('status')
        item.meta._set_attributes(**request.get('meta'))
        app.log.debug(item.meta)
        try:
            item.my_format= item.poll_format()
            item_val['PollFormat'] = item.my_format
            _log.info(item.my_format)
        except:
            import traceback
            _log.error(traceback.format_exc())

    if(request.get('image') is not None):
        item_val['Image']= request.get('image')
        item.image = request.get('image')
    stat = get_stat(response[0])
    if stat is not None:
        item.pat_stats= stat
        item_val['PatStats']=stat
    return dynamodb_table.put_item(
        Item =item_val,
        ReturnValues="ALL_OLD"
    )

@app.route('/character',methods = ['DELETE'])
def remove_character():
    request = app.current_request.json_body
    answer=dynamodb_table.query(IndexName='infoOrCharacterIDIndex',
    KeyConditionExpression=Key('SortKey').eq(request.get('sortKey')))
    print(answer)
    return dynamodb_table.delete_item(Key={'PartKey':answer['Items'][0]['PartKey'],
    'SortKey':answer['Items'][0]['SortKey']})
def find_by_discordId(request):
    return dynamodb_table.query(IndexName='discordIdIndex',
    KeyConditionExpression=Key("DiscordId").eq(str(request.get('discordId'))),
    FilterExpression=Attr('SortKey').eq('INFO'),
    Limit=1)
def find_by_discordId_pynamo(request):
    return [ x for x in Patron.discord_index.query(str(request.get('discordId')), filter_condition=Patron.sort_key=='INFO')]
def find_by_userId(request):
    return [x for x in Patron.user_index.query(str(request.get('userId')),filter_condition=Patron.sort_key=='INFO')]
@app.route('/member',methods=['PUT'])
def find_member():
    request = app.current_request.json_body
    response = None
    if request.get('discordId') !=None:
        response =find_by_discordId_pynamo(request)
        if len(response) == 0:
            return Response(body={'message': 'DiscordId did not refer to a patron'}, status_code=400, headers={'Content-Type':'application/json'})
    elif request.get('userId') != None:
        response = find_by_userId(request)
        if len(response)==0:
            return Response(body={'message': 'UserId did not refer to a patron'}, status_code=400, headers={'Content-Type':'application/json'})
    return response[0].to_json()

@app.route("/poll",methods=['PUT'])
def get_poll():
    try:
        return [ x.to_json() for x in Patron.cat_index.query(app.current_request.json_body.get('category','Cartoons'),filter_condition=Patron.pat_stats.exists() and Patron.meta.contains(Patron.meta.status))]
    except:
        app.log.error(traceback.format_exc())
        return  [ x.to_json() for x in Patron.cat_index.query(app.current_request.json_body.get('category','Cartoons'),filter_condition=Patron.pat_stats.exists())]
    # return dynamodb_table.query(IndexName='Category-CreationDate-index',
    # KeyConditionExpression=Key('Category').eq(app.current_request.json_body.get('category','Cartoons')),
    # FilterExpression=Attr('PatStats').exists())['Items']

def parseJSONAPI(member:JSONAPIResource):
    patron = dict();
    grab_discord_id = lambda x: x.attribute('social_connections').get('discord').get('user_id',None)
    has_discord = lambda x: x.attribute('social_connections').get('discord') is not None;
    # The creator, apparently, isn't in the system
    if(member.attribute("patron_status") is not None):
        patron['Status'] = member.attribute("patron_status")
        if(member.relationship("currently_entitled_tiers") is not None):
            if(len(member.relationship("currently_entitled_tiers"))>0):
                if(member.relationship("currently_entitled_tiers")[0].attribute('title') is not None):
                    patron['Tier'] = [ x.attribute('title') for x in member.relationship("currently_entitled_tiers")]
                    # print(member.relationship("currently_entitled_tiers")[0].attribute('title'))
    if(member.relationship('user') is not None):
        if(member.relationship('user').attribute('social_connections') is not None):
            if(has_discord(member.relationship('user'))):
                patron['DiscordId'] = grab_discord_id(member.relationship('user'))

    if(member.attribute("full_name") is not None):
        patron['Name'] = member.attribute("full_name")
    patron['PartKey'] = "PATREON_" + member.id()
    patron['PatronId']=member.id()
    patron['SortKey']="INFO"
    return patron;
# from chalice.test import Client
# with Client(app) as client:
#     with open('chalicelib/example.json','rb') as f:
#         response = client.http.put('/character',body=f.read(),headers={'Content-Type':'application/json'})
#         assert response.status_code == 200

_T = TypeVar('_T')
_T1 = TypeVar('_T1')

def get_stat(pat:Patron):
    if pat.htier is not None:
        return tier_enum.get(pat.htier).code
    if pat.status in ["Override","OVERRIDE"]:
        return "YEP"
