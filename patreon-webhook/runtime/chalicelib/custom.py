from datetime import datetime, timezone
from dateutil.parser import parse
from pynamodb.attributes import Attribute
from pynamodb.constants import STRING
from typing import Union
class AWSISODateTimeAttribute(Attribute[datetime]):
    attr_type = STRING

    def serialize(self, value: Union[datetime,str]) -> str:
        t: datetime = None
        if isinstance(value, str):
            t = parse(value)
        else:
            t = value
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace("+00:00", "Z")

    def deserialize(self, value: str) -> str:
        return value