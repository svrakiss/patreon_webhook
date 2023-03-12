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
patch_all()
app = Chalice(app_name='patreon-webhook')
dynamodb = boto3.resource('dynamodb')
dynamodb_table = dynamodb.Table(os.environ.get('APP_TABLE_NAME', ''))
ssmclient = boto3.client('ssm')
xray_recorder.begin_segment('init')
secret = ssmclient.get_parameter(Name='/config/patreon-webhook/secret',WithDecryption=True)
secret:str  = secret['Parameter']['Value']
xray_recorder.end_segment()
@app.route('/callback', methods=['POST','GET','PUT'])

def webhook_callback():
    request = app.current_request.json_body
    raw_body = app.current_request.raw_body
    try:
        # print(app.current_request.headers.get('X-Patreon-Signature'))
        # print(f'raw body {raw_body}')
        # hmac_test =hmac.new(bytes(secret,'utf-8'),msg=raw_body,digestmod='md5')
        # print(f'hmac normal digest: {hmac_test.digest()}')
        # print(f'hex digest: {hmac_test.hexdigest()}')
        if(not hmac.compare_digest(app.current_request.headers.get('X-Patreon-Signature'),
        hmac.new(key=bytes(secret,'utf-8'),msg=raw_body,digestmod='md5').hexdigest())):
            return Response(body={'message':'UnAuthorized'},  status_code=401, headers={'Content-Type':'application/json'})
        print("Passed the test")
    except:
        print("Exception thrown")
        pass
    print(str(request))
    member = JSONAPIParser(request)
    member_response = parseJSONAPI(member.data())
    updateExp= 'SET Tier= :tier_val'
    attVals = { ':tier_val':member_response.get('Tier',[])}
    if member_response.get('CreationDate') is not None:
        updateExp+=', CreationDate= :create_val'
        attVals[':create_val']=member_response.get("CreationDate")
    if(member_response.get('DiscordId') is not None):
        updateExp= updateExp + ', DiscordId= :discord_val'
        attVals[':discord_val'] = member_response.get('DiscordId')
    if(member_response.get('UserId') !=None):
        updateExp = updateExp + ', UserId= :user_val'
        attVals[':user_val'] = member_response.get('UserId')
    if member_response.get('Status') !=None:
        attVals[':status_val']=member_response.get('Status')
        updateExp = updateExp + ', #StatusAtt = :status_val' 
        return dynamodb_table.update_item(Key = {"PartKey":member_response.get('PartKey'),"SortKey":member_response.get('SortKey')},
        UpdateExpression=updateExp,
        ExpressionAttributeNames={"#StatusAtt":"Status"},
        ExpressionAttributeValues=attVals
        , ReturnValues="ALL_NEW"
        )
    return dynamodb_table.update_item(
        Key = {"PartKey":member_response.get('PartKey'),"SortKey":member_response.get('SortKey')},
        UpdateExpression=updateExp,
        ExpressionAttributeValues=attVals,
        ReturnValues="ALL_NEW"
    )

@app.route('/character',methods = ['POST','PUT'])
def add_character():
    request = app.current_request.json_body
    response =find_by_discordId(request)['Items']
    if len(response) == 0:
        return Response(body={'message': 'DiscordId did not refer to a patron'}, status_code=400, headers={'Content-Type':'application/json'})
    item_val={"PartKey": response[0]['PartKey'], "SortKey": request.get('sortKey'), 'CharacterName':request.get('characterName')}
    if(request.get('category') is not None):
        item_val['Category']= request.get('category')
    if(request.get('creationDate') is not None):
        datetime.fromisoformat(request.get('creationDate')) # so that it will be validated
        item_val['CreationDate'] =request.get('creationDate')

    if(request.get('meta') is not None):
        item_val['CharacterMeta'] = { 'Artist':request.get('meta').get('artist',None),'Source':request.get('meta').get('source',None),'Comments':request.get('meta').get('comments',None)}
    if(request.get('image') is not None):
        item_val['Image']= request.get('image')

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
    FilterExpression=Attr('SortKey').eq('INFO'))
@app.route('/member',methods=['PUT'])
def find_member():
    request = app.current_request.json_body
    response= find_by_discordId(request)['Items']
    if len(response) == 0:
        return Response(body={'message': 'DiscordId did not refer to a patron'}, status_code=400, headers={'Content-Type':'application/json'})
    return response

def parseJSONAPI(member:JSONAPIResource):
    patron = dict();
    grab_discord_id = lambda x: x.attribute('social_connections').get('discord').get('user_id',None)
    has_discord = lambda x: x.attribute('social_connections').get('discord') is not None;

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
        patron['UserId'] = member.relationship('user').id()
    if(member.attribute("full_name") is not None):
        patron['Name'] = member.attribute("full_name")
    patron['PartKey'] = "PATREON_" + member.id()
    patron['PatronId']=member.id()
    patron['SortKey']="INFO"
    patron['CreationDate']=datetime.utcnow().isoformat(timespec='milliseconds').replace("+00:00", "Z")
    return patron;
