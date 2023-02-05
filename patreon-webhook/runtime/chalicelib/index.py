from pynamodb.indexes import GlobalSecondaryIndex, AllProjection
from pynamodb.attributes import UnicodeAttribute
from chalicelib.custom import AWSISODateTimeAttribute
class CategoryIndex(GlobalSecondaryIndex):
    class Meta:
        index_name='Category-CreationDate-index'
        projection=AllProjection()
        read_capacity_units = 2
        write_capacity_units = 1
    category = UnicodeAttribute(hash_key=True,attr_name="Category")
    creation_date = AWSISODateTimeAttribute(range_key=True,attr_name="CreationDate")