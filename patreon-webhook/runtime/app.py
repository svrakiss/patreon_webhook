import os
import boto3
from chalice import Chalice
from patreon.jsonapi.parser import JSONAPIParser, JSONAPIResource
import hmac
app = Chalice(app_name='patreon-webhook')
dynamodb = boto3.resource('dynamodb')
dynamodb_table = dynamodb.Table(os.environ.get('APP_TABLE_NAME', ''))
ssmclient = boto3.client('ssm')
secret = ssmclient.get_parameter(Name='/config/patreon-webhook/secret',WithDecryption=True)
secret:str  = secret['Parameter']['Value']
@app.route('/callback', methods=['POST','GET','PUT'])

def webhook_callback():
    request = app.current_request.json_body
    raw_body = app.current_request.raw_body
    try:
        print(app.current_request.headers.get('X-Patreon-Signature'))
        print(f'raw body {raw_body}')
        hmac_test =hmac.new(bytes(secret,'utf-8'),msg=raw_body,digestmod='md5')
        print(f'hmac normal digest: {hmac_test.digest()}')
        print(f'hex digest: {hmac_test.hexdigest()}')
        if(not hmac.compare_digest(app.current_request.headers.get('X-Patreon-Signature'),
        hmac.new(key=bytes(secret,'utf-8'),msg=raw_body,digestmod='md5').hexdigest())):
            print("should abort")
        print("Passed the test")
    except:
        print("Exception thrown")
        pass
    print(str(request))
    member = JSONAPIParser(request)
    member_response = parseJSONAPI(member.data())
    updateExp= 'SET #StatusAtt = :status_val, Tier= :tier_val'
    attVals = {':status_val':member_response.get('Status'), ':tier_val':member_response.get('Tier',[])}
    if(member_response.get('DiscordId') is not None):
        updateExp= updateExp + ', DiscordId= :discord_val'
        attVals[':discord_val'] = member_response.get('DiscordId')
    return dynamodb_table.update_item(Key = {"PartKey":member_response.get('PartKey'),"SortKey":member_response.get('SortKey')},
    UpdateExpression=updateExp,
    ExpressionAttributeNames={"#StatusAtt":"Status"},
     ExpressionAttributeValues=attVals
     , ReturnValues="ALL_NEW"
    )

@app.route('/character',methods = ['POST','PUT'])
def add_character():
    request = app.current_request.json_body
    return dynamodb_table.query(IndexName='discordIdIndex',
    KeyConditions={"DiscordId": 
    {'AttributeValueList':[str(request.get('discordId')  ) ],
    'ComparisonOperator':'EQ'}})

def parseJSONAPI(member:JSONAPIResource):
    patron = dict();
    grab_discord_id = lambda x: x.attribute('social_connections').get('discord').get('user_id',None)
    has_discord = lambda x: x.attribute('social_connections').get('discord') is not None;

    if(member.attribute("patron_status") is None):
        # this is probably the creator
        patron['Status']="override"
    else:
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
