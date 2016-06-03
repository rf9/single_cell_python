import sys
from collections import defaultdict

import requests
from requests.exceptions import HTTPError

# MATERIAL_ROOT_URL = 'http://0.0.0.0:3000/api/v1/'
# CONTAINER_ROOT_URL = 'http://0.0.0.0:3001/api/v1/

MATERIAL_ROOT_URL = 'http://dev.psd.sanger.ac.uk:7463/api/v1/'
CONTAINER_ROOT_URL = 'http://dev.psd.sanger.ac.uk:7464/api/v1/'


class ApiObject:
    _cache = defaultdict(lambda: {})

    def __init__(self, root=None, type=None, id=None, attributes=None, relationships=None, loaded=False):
        self.root = root
        self.type = type or self.type
        self.id = id
        self._attributes = attributes or {}
        self._relationships = relationships or {}
        self.loaded = loaded

        if loaded:
            self._add_to_cache()

    def _add_to_cache(self):
        self._cache[self.type][self.id] = self

    def get(self, key):
        if not self.loaded:
            self.load()

        if key in self._attributes:
            return self._attributes[key]
        if key in self._relationships:
            return self._relationships[key]

    def set(self, key, value):
        if not self.loaded:
            self.load()

        if key in self._attributes:
            self._attributes[key] = value
            return self._attributes[key]
        if key in self._relationships:
            self._relationships[key] = value
            return self._relationships[key]

        if isinstance(value, list) or isinstance(value, ApiObject):
            self._relationships[key] = value
            return self._relationships[key]
        else:
            self._attributes[key] = value
            return self._attributes[key]

    def attributes(self):
        if not self.loaded:
            self.load()

        return self._attributes

    def relationships(self):
        if not self.loaded:
            self.load()

        return self._relationships

    def to_json(self):
        if not self.loaded:
            self.load(allow_request=False)

        return {
            'id': self.id,
            'attributes': self._attributes,
            'relationships': {
                type: {'data': [object.to_json() for object in data] if isinstance(data, list) else data.to_json()}
                for (type, data) in self._relationships.items()
                }
        }

    def save(self):
        url = self.root + self.type + '/'
        json = {
            'data': self.to_json()
        }
        if self.id is None:
            r = requests.post(url, json=json)
        else:
            r = requests.put(url + self.id, json=json)

        try:
            r.raise_for_status()
        except HTTPError as err:
            print(r.text, file=sys.stderr)
            raise err

        json = r.json()
        self.id = json['data']['id']
        [ApiObject._from_json(obj) for obj in json['included']]
        ApiObject._from_json(json['data'])
        self.load()

    @classmethod
    def _from_json(cls, json):
        try:
            attributes = json['attributes']
        except KeyError:
            attributes = {}

        relationships = {}
        if 'relationships' in json:
            for field, value in json['relationships'].items():
                if isinstance(value['data'], list):
                    relationships[field] = [cls.find(None, ref['type'], ref['id']) for ref in value['data']]
                else:
                    relationships[field] = cls.find(None, value['data']['type'], value['data']['id'])

        return ApiObject(type=json['type'], id=json['id'], attributes=attributes, relationships=relationships, loaded=True)

    @classmethod
    def find(cls, root, type, id):
        return ApiObject(root=root, type=type, id=id, loaded=False)

    def load(self, allow_request=True):
        try:
            object = self._cache[self.type][self.id]
        except KeyError:
            if not allow_request:
                return

            url = self.root + self.type + '/' + str(self.id)
            json = requests.get(url).json()

            if 'included' in json:
                [ApiObject._from_json(obj) for obj in json['included']]

            object = self._from_json(json['data'])

        self._attributes = object._attributes
        self._relationships = object._relationships
        self._add_to_cache()
        self.loaded = True

        return self

    @classmethod
    def where(cls, root, type, queries):
        url = root + type
        if queries:
            url += '?' + '&'.join([key + '=' + value for (key, value) in queries.items()])
        json = requests.get(url).json()

        if 'included' in json:
            [ApiObject._from_json(obj) for obj in json['included']]

        return [cls._from_json(data) for data in json['data']]

    @classmethod
    def find_by(cls, root, type, queries):
        data = cls.where(root, type, queries)

        if data:
            return data[0]
        else:
            raise LookupError()
