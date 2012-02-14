import datetime
import re
from humongolus import Field, FieldException, Document, import_class
from pymongo.objectid import ObjectId

class MinException(FieldException): pass
class MaxException(FieldException): pass

def parse_phone(number):
    try:
        phonePattern = re.compile(r'''
                        # don't match beginning of string, number can start anywhere
            (\d{3})     # area code is 3 digits (e.g. '800')
            \D*         # optional separator is any number of non-digits
            (\d{3})     # trunk is 3 digits (e.g. '555')
            \D*         # optional separator
            (\d{4})     # rest of number is 4 digits (e.g. '1212')
            \D*         # optional separator
            (\d*)       # extension is optional and can be any number of digits
            $           # end of string
            ''', re.VERBOSE)
        res = phonePattern.search(number).groups()
        st = "".join(res)
        if st.startswith("1"): return "+%s" % st
        else: return "+1%s" % st
    except Exception as e:
        raise e

class Char(Field):
    _max=None
    _min=None
    _type = unicode
    _display = "string"

    def clean(self, val, doc=None):
        try:            
            val = self._type(val)
            if self._max != None and len(val) > self._max: raise MaxException("must be less than %s" % self._max)
            if self._min != None and len(val) < self._min: raise MinException("must be greater than %s" % self._min)
            return val
        except FieldException as e: raise e
        except: raise FieldException("%s is not a valid %s" % (val, self._display))

class Integer(Char):
    _type=int
    _display="integer"

    def clean(self, val, doc=None):
        try:            
            val = self._type(val)
            if self._max != None and val > self._max: raise MaxException("must be less than %s" % self._max)
            if self._min != None and val < self._min: raise MinException("must be greater than %s" % self._min)
            return val
        except FieldException as e: raise e
        except: raise FieldException("%s is not a valid %s" % (val, self._display))

class Float(Integer):
    _type=float
    _display="float"

class Date(Field):

    def clean(self, val, doc=None):
        try:
            if isinstance(val, datetime.datetime): return val
            return datetime.datetime(val)
        except: raise FieldException("%s: invalid datetime" % val)


class Boolean(Field):

    def clean(self, val, doc=None):
        try:
            if isinstance(val, bool): return val
            return bool(val)
        except: raise FieldException("%s invalid boolean" % val)

class Geo(Field):
    def clean(self, val, doc=None):
        try:
            if isinstance(val, list):
                if len(val) == 2:
                    return val
                else: raise FieldException("to many values: %s" % val)
            else: raise FieldException("must be type array")
        except: raise FieldException("%s must be array" % val)

class TimeStamp(Date):

    def _save(self, namespace):
        if self._value == None:
            self._value = datetime.datetime.utcnow()
        
        return super(TimeStamp, self)._save(namespace)

class DocumentId(Field):
    _type = None

    def clean(self, val, doc=None):
        val = val._id if hasattr(val, '_id') else val
        if val: 
            v = ObjectId(val)
        else: raise FieldException("value cannot be None")
        return v
    
    def __call__(self):
        if not self._value is None and self._type:
            return self._type(id=self._value)
        else: raise FieldException("Cannot instantiate %s with id %s" % (self._type, self._value))


class AutoIncrement(Integer):
    _collection = None

    def _save(self, namespace):
        if self._value == None:
            col = self._collection if self._collection else "sequence"
            res = self._conn["auto_increment"][col].find_and_modify({"field":self._name}, {"$inc":{"val":1}}, upsert=True, new=True, fields={"val":True})
            self._value = res['val']
        
        return super(AutoIncrement, self)._save(namespace)

class DynamicDocument(Field):

    def clean(self, val, doc=None):
        if isinstance(val, Document):
            if val._id != None:
                cls = "%s.%s" % (val.__module__, val.__class__.__name__)
                return {"cls":cls, "_id":val._id}
            else: raise FieldException("Document does not have an id. Be sure to save first.")
        elif isinstance(val, dict): 
            return val
        else: raise FieldException("%s is not a valid document type" % val.__class__.__name__)
    
    def __call__(self):
        if isinstance(self._value, dict):
            cls = import_class(self._value['cls'])
            return cls(id=self._value['_id'])
        else: raise Exception("Bad Value: %s" % self._value)


class Regex(Char):
    _reg = None
    _disp_error = None

    def clean(self, val, doc=None):
        val = super(Regex, self).clean(val, doc)
        if not self._reg.search(val): raise FieldException("%s: pattern not found" % val if not self._disp_error else self._disp_error)
        return val

class Email(Regex):
    _disp_rror = "Invalid Email Address"
    _reg = re.compile(
    r"(^[-!#$%&'*/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"' # quoted-string
    r')@(?:[A-Z0-9-]+\.)+[A-Z]{2,6}$', re.IGNORECASE)  # domain

class Phone(Char):

    def clean(self, val, doc=None):
        val = super(Phone, self).clean(val, doc)
        try:
            return parse_phone(val)
        except: raise FieldException("%s is not a valid format" % val)