from __future__ import absolute_import, division, print_function

import datetime
import json
from copy import deepcopy

import ten99policy
from ten99policy import api_requestor, util, six


def _compute_diff(current, previous):
    if isinstance(current, dict):
        previous = previous or {}
        diff = current.copy()
        for key in set(previous.keys()) - set(diff.keys()):
            diff[key] = ""
        return diff
    return current if current is not None else ""


def _serialize_list(array, previous):
    array = array or []
    previous = previous or []
    params = {}

    for i, v in enumerate(array):
        previous_item = previous[i] if len(previous) > i else None
        if hasattr(v, "serialize"):
            params[str(i)] = v.serialize(previous_item)
        else:
            params[str(i)] = _compute_diff(v, previous_item)

    return params


class Ten99PolicyObject(dict):
    class ReprJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime.datetime):
                return api_requestor._encode_datetime(obj)
            return super(Ten99PolicyObject.ReprJSONEncoder, self).default(obj)

    def __init__(
        self,
        id=None,
        api_key=None,
        ten99policy_version=None,
        ten99policy_environment=None,
        last_response=None,
        **params
    ):
        super(Ten99PolicyObject, self).__init__()

        self._unsaved_values = set()
        self._transient_values = set()
        self._last_response = last_response

        self._retrieve_params = params
        self._previous = None

        object.__setattr__(self, "api_key", api_key)
        object.__setattr__(self, "ten99policy_version", ten99policy_version)
        object.__setattr__(self, "ten99policy_environment", ten99policy_environment)

        if id:
            self["id"] = id

    @property
    def last_response(self):
        return self._last_response

    def update(self, update_dict):
        for k in update_dict:
            self._unsaved_values.add(k)

        return super(Ten99PolicyObject, self).update(update_dict)

    def __setattr__(self, k, v):
        if k[0] == "_" or k in self.__dict__:
            return super(Ten99PolicyObject, self).__setattr__(k, v)

        self[k] = v
        return None

    def __getattr__(self, k):
        if k[0] == "_":
            raise AttributeError(k)

        try:
            return self[k]
        except KeyError as err:
            raise AttributeError(*err.args)

    def __delattr__(self, k):
        if k[0] == "_" or k in self.__dict__:
            return super(Ten99PolicyObject, self).__delattr__(k)
        else:
            del self[k]

    def __setitem__(self, k, v):
        if v == "":
            raise ValueError(
                "You cannot set %s to an empty string. "
                "We interpret empty strings as None in requests."
                "You may set %s.%s = None to delete the property" % (k, str(self), k)
            )

        # Allows for unpickling in Python 3.x
        if not hasattr(self, "_unsaved_values"):
            self._unsaved_values = set()

        self._unsaved_values.add(k)

        super(Ten99PolicyObject, self).__setitem__(k, v)

    def __getitem__(self, k):
        try:
            return super(Ten99PolicyObject, self).__getitem__(k)
        except KeyError as err:
            if k in self._transient_values:
                raise KeyError(
                    "%r.  HINT: The %r attribute was set in the past."
                    "It was then wiped when refreshing the object with "
                    "the result returned by Ten99Policy's API, probably as a "
                    "result of a save().  The attributes currently "
                    "available on this object are: %s"
                    % (k, k, ", ".join(list(self.keys())))
                )
            else:
                raise err

    def __delitem__(self, k):
        super(Ten99PolicyObject, self).__delitem__(k)

        # Allows for unpickling in Python 3.x
        if hasattr(self, "_unsaved_values") and k in self._unsaved_values:
            self._unsaved_values.remove(k)

    # Custom unpickling method that uses `update` to update the dictionary
    # without calling __setitem__, which would fail if any value is an empty
    # string
    def __setstate__(self, state):
        self.update(state)

    # Custom pickling method to ensure the instance is pickled as a custom
    # class and not as a dict, otherwise __setstate__ would not be called when
    # unpickling.
    def __reduce__(self):
        reduce_value = (
            type(self),  # callable
            (  # args
                self.get("id", None),
                self.api_key,
                self.ten99policy_version,
                self.ten99policy_environment,
            ),
            dict(self),  # state
        )
        return reduce_value

    @classmethod
    def construct_from(
        cls,
        values,
        key,
        ten99policy_version=None,
        ten99policy_environment=None,
        last_response=None,
    ):
        # Deserialize any stringified JSON values
        for k, v in values.items():
            if isinstance(v, str):
                try:
                    # Replace single quotes with double quotes and parse the JSON string
                    values[k] = json.loads(v.replace("'", '"'))
                except json.JSONDecodeError:
                    pass  # Keep the original string if it can't be parsed

        instance = cls(
            values.get("id"),
            api_key=key,
            ten99policy_version=ten99policy_version,
            ten99policy_environment=ten99policy_environment,
            last_response=last_response,
        )
        instance.refresh_from(
            values,
            api_key=key,
            ten99policy_version=ten99policy_version,
            ten99policy_environment=ten99policy_environment,
            last_response=last_response,
        )
        return instance

    def refresh_from(
        self,
        values,
        api_key=None,
        partial=False,
        ten99policy_version=None,
        ten99policy_environment=None,
        last_response=None,
    ):
        self.api_key = api_key or getattr(values, "api_key", None)
        self.ten99policy_version = ten99policy_version or getattr(
            values, "ten99policy_version", None
        )
        self.ten99policy_environment = ten99policy_environment or getattr(
            values, "ten99policy_environment", None
        )
        self._last_response = last_response or getattr(values, "_last_response", None)

        # Wipe old state before setting new.  This is useful for e.g.
        # updating a customer, where there is no persistent card
        # parameter.  Mark those values which don't persist as transient
        if partial:
            self._unsaved_values = self._unsaved_values - set(values)
        else:
            removed = set(self.keys()) - set(values)
            self._transient_values = self._transient_values | removed
            self._unsaved_values = set()
            self.clear()

        self._transient_values = self._transient_values - set(values)

        # if not isinstance(values, dict):
        #     return values

        for k, v in six.iteritems(values):
            super(Ten99PolicyObject, self).__setitem__(
                k,
                util.convert_to_ten99policy_object(
                    v, api_key, ten99policy_version, ten99policy_environment
                ),
            )

        self._previous = values

    @classmethod
    def api_base(cls):
        return None

    def request(self, method, url, params=None, headers=None):
        if params is None:
            params = self._retrieve_params
        requestor = api_requestor.APIRequestor(
            key=self.api_key,
            api_base=self.api_base(),
            api_version=self.ten99policy_version,
            environment=self.ten99policy_environment,
        )
        response, api_key = requestor.request(method, url, params, headers)

        return util.convert_to_ten99policy_object(
            response, api_key, self.ten99policy_version, self.ten99policy_environment
        )

    def request_stream(self, method, url, params=None, headers=None):
        if params is None:
            params = self._retrieve_params
        requestor = api_requestor.APIRequestor(
            key=self.api_key,
            api_base=self.api_base(),
            api_version=self.ten99policy_version,
            environment=self.ten99policy_environment,
        )
        response, _ = requestor.request_stream(method, url, params, headers)

        return response

    def __repr__(self):
        ident_parts = [type(self).__name__]

        if isinstance(self.get("object"), six.string_types):
            ident_parts.append(self.get("object"))

        if isinstance(self.get("id"), six.string_types):
            ident_parts.append("id=%s" % (self.get("id"),))

        unicode_repr = "<%s at %s> JSON: %s" % (
            " ".join(ident_parts),
            hex(id(self)),
            str(self),
        )

        if six.PY2:
            return unicode_repr.encode("utf-8")
        else:
            return unicode_repr

    def __str__(self):
        return json.dumps(
            self.to_dict_recursive(),
            sort_keys=True,
            indent=2,
            cls=self.ReprJSONEncoder,
        )

    def to_dict(self):
        return dict(self)

    def to_dict_recursive(self):
        def maybe_to_dict_recursive(value):
            if value is None:
                return None
            elif isinstance(value, Ten99PolicyObject):
                return value.to_dict_recursive()
            else:
                return value

        return {
            key: (
                list(map(maybe_to_dict_recursive, value))
                if isinstance(value, list)
                else maybe_to_dict_recursive(value)
            )
            for key, value in six.iteritems(dict(self))
        }

    @property
    def ten99policy_id(self):
        return self.id

    def serialize(self, previous):
        params = {}
        unsaved_keys = self._unsaved_values or set()
        previous = previous or self._previous or {}

        for k, v in six.iteritems(self):
            if k == "id" or (isinstance(k, str) and k.startswith("_")):
                continue
            elif isinstance(v, ten99policy.api_resources.abstract.APIResource):
                continue
            elif hasattr(v, "serialize"):
                child = v.serialize(previous.get(k, None))
                if child != {}:
                    params[k] = child
            elif k in unsaved_keys:
                params[k] = _compute_diff(v, previous.get(k, None))
            elif k == "additional_owners" and v is not None:
                params[k] = _serialize_list(v, previous.get(k, None))

        return params

    # This class overrides __setitem__ to throw exceptions on inputs that it
    # doesn't like. This can cause problems when we try to copy an object
    # wholesale because some data that's returned from the API may not be valid
    # if it was set to be set manually. Here we override the class' copy
    # arguments so that we can bypass these possible exceptions on __setitem__.
    def __copy__(self):
        copied = Ten99PolicyObject(
            self.get("id"),
            self.api_key,
            ten99policy_version=self.ten99policy_version,
            ten99policy_environment=self.ten99policy_environment,
        )

        copied._retrieve_params = self._retrieve_params

        for k, v in six.iteritems(self):
            # Call parent's __setitem__ to avoid checks that we've added in the
            # overridden version that can throw exceptions.
            super(Ten99PolicyObject, copied).__setitem__(k, v)

        return copied

    # This class overrides __setitem__ to throw exceptions on inputs that it
    # doesn't like. This can cause problems when we try to copy an object
    # wholesale because some data that's returned from the API may not be valid
    # if it was set to be set manually. Here we override the class' copy
    # arguments so that we can bypass these possible exceptions on __setitem__.
    def __deepcopy__(self, memo):
        copied = self.__copy__()
        memo[id(self)] = copied

        for k, v in six.iteritems(self):
            # Call parent's __setitem__ to avoid checks that we've added in the
            # overridden version that can throw exceptions.
            super(Ten99PolicyObject, copied).__setitem__(k, deepcopy(v, memo))

        return copied
