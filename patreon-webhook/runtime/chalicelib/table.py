from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute,MapAttribute, ListAttribute, UTCDateTimeAttribute
import os
from chalicelib.custom import AWSISODateTimeAttribute
from chalicelib.index import CategoryIndex,UserIdIndex,DiscordIdIndex,PollIndex
class CharacterMeta(MapAttribute):
    source = UnicodeAttribute(null = True,attr_name="Source")
    artist = UnicodeAttribute(null = True,attr_name="Artist")
    comments = UnicodeAttribute(null = True,attr_name="Comments")
    image= UnicodeAttribute(null=True,attr_name="Image")
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
    user_id= UnicodeAttribute(null=True,attr_name="UserId")
    cat_index = CategoryIndex()
    user_index= UserIdIndex()
    discord_index=DiscordIdIndex()
    my_format = UnicodeAttribute(null=True,attr_name="PollFormat")
    htier= UnicodeAttribute(null=True,attr_name="HTier")
    poll_index=PollIndex()
    def poll_format(self):
        artist_is_provided =self.meta.artist is not None
        source_is_provided = self.meta.source is not None
        if  artist_is_provided and source_is_provided:
            return f"{self.character_name} ({self.meta.artist} | {self.meta.source})"
        elif artist_is_provided:
            return f"{self.character_name} ({self.meta.artist})"
        elif source_is_provided:
            return f"{self.character_name} ({self.meta.source })"
        else:
           return self.character_name
