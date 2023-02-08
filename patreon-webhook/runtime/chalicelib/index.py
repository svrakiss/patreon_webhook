from pynamodb.indexes import GlobalSecondaryIndex, AllProjection,IncludeProjection
from pynamodb.attributes import UnicodeAttribute,ListAttribute
from chalicelib.custom import AWSISODateTimeAttribute
class CategoryIndex(GlobalSecondaryIndex):
    class Meta:
        index_name='Category-CreationDate-index'
        projection=AllProjection()
        read_capacity_units = 2
        write_capacity_units = 1
    category = UnicodeAttribute(hash_key=True,attr_name="Category")
    creation_date = AWSISODateTimeAttribute(range_key=True,attr_name="CreationDate")
class UserIdIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = 'UserId-index'
        projection = IncludeProjection(['PartKey','SortKey','Tier','Status'])
        read_capacity_units = 2
        write_capacity_units = 1
    user_id= UnicodeAttribute(hash_key=True,attr_name="UserId")
    tier = ListAttribute(null = True,attr_name="Tier")
    part_key = UnicodeAttribute(hash_key=True,attr_name="PartKey")
    sort_key = UnicodeAttribute(range_key=True,attr_name="SortKey")
    status = UnicodeAttribute(null=True,attr_name="Status")

class DiscordIdIndex(GlobalSecondaryIndex):
    class Meta:
        index_name= 'discordIdIndex'
        projection = AllProjection()
        read_capacity_units = 2
        write_capacity_units = 1
    discord_id = UnicodeAttribute(hash_key=True,attr_name="DiscordId")
