from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute,MapAttribute, ListAttribute, UTCDateTimeAttribute
import os
from chalicelib.custom import AWSISODateTimeAttribute
class CharacterMeta(MapAttribute):
    source = UnicodeAttribute(null = True)
    artist = UnicodeAttribute(null = True)
    comments = UnicodeAttribute(null = True)
class Patron(Model):
    class Meta:
        table_name = os.environ.get("APP_TABLE_NAME")
    part_key = UnicodeAttribute(hash_key=True,attr_name="PartKey")
    sort_key = UnicodeAttribute(range_key=True,attr_name="SortKey")
    discord_id = UnicodeAttribute(null = True,attr_name="DiscordId")
    patron_id = UnicodeAttribute(null = True,attr_name="PatronId")
    category = UnicodeAttribute(null = True,attr_name="Category")
    meta = CharacterMeta(attr_name="CharacterMeta",default={})
    tier = ListAttribute(null = True,attr_name="Tier")
    creation_date = AWSISODateTimeAttribute(null = True,attr_name="CreationDate")
    pat_stats = UnicodeAttribute(null = True,attr_name="PatStats")
    status = UnicodeAttribute(null=True,attr_name="Status")
    character_name = UnicodeAttribute(null=True,attr_name="CharacterName")
    image = UnicodeAttribute(null=True,attr_name="Image")
    name = UnicodeAttribute(null = True,attr_name="Name")