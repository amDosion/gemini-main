# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Common utilities for the SDK."""

import base64
import collections.abc
import datetime
import enum
import functools
import logging
import re
import typing
from typing import Any, Callable, FrozenSet, Optional, Union, get_args, get_origin
import uuid
import warnings
import pydantic
from pydantic import alias_generators
from typing_extensions import TypeAlias

logger = logging.getLogger('google_genai._common')

StringDict: TypeAlias = dict[str, Any]


class ExperimentalWarning(Warning):
  """Warning for experimental features."""


def set_value_by_path(
    data: Optional[dict[Any, Any]], keys: list[str], value: Any
) -> None:
  """Examples:

  set_value_by_path({}, ['a', 'b'], v)
    -> {'a': {'b': v}}
  set_value_by_path({}, ['a', 'b[]', c], [v1, v2])
    -> {'a': {'b': [{'c': v1}, {'c': v2}]}}
  set_value_by_path({'a': {'b': [{'c': v1}, {'c': v2}]}}, ['a', 'b[]', 'd'], v3)
    -> {'a': {'b': [{'c': v1, 'd': v3}, {'c': v2, 'd': v3}]}}
  """
  if value is None:
    return
  for i, key in enumerate(keys[:-1]):
    if key.endswith('[]'):
      key_name = key[:-2]
      if data is not None and key_name not in data:
        if isinstance(value, list):
          data[key_name] = [{} for _ in range(len(value))]
        else:
          raise ValueError(
              f'value {value} must be a list given an array path {key}'
          )
      if isinstance(value, list) and data is not None:
        for j, d in enumerate(data[key_name]):
          set_value_by_path(d, keys[i + 1 :], value[j])
      else:
        if data is not None:
          for d in data[key_name]:
            set_value_by_path(d, keys[i + 1 :], value)
      return
    elif key.endswith('[0]'):
      key_name = key[:-3]
      if data is not None and key_name not in data:
        data[key_name] = [{}]
      if data is not None:
        set_value_by_path(data[key_name][0], keys[i + 1 :], value)
      return
    if data is not None:
      data = data.setdefault(key, {})

  if data is not None:
    existing_data = data.get(keys[-1])
    # If there is an existing value, merge, not overwrite.
    if existing_data is not None:
      # Don't overwrite existing non-empty value with new empty value.
      # This is triggered when handling tuning datasets.
      if not value:
        pass
      # Don't fail when overwriting value with same value
      elif value == existing_data:
        pass
      # Instead of overwriting dictionary with another dictionary, merge them.
      # This is important for handling training and validation datasets in tuning.
      elif isinstance(existing_data, dict) and isinstance(value, dict):
        # Merging dictionaries. Consider deep merging in the future.
        existing_data.update(value)
      else:
        raise ValueError(
            f'Cannot set value for an existing key. Key: {keys[-1]};'
            f' Existing value: {existing_data}; New value: {value}.'
        )
    else:
      if (
          keys[-1] == '_self'
          and isinstance(data, dict)
          and isinstance(value, dict)
      ):
        data.update(value)
      else:
        data[keys[-1]] = value


def get_value_by_path(
    data: Any, keys: list[str], *, default_value: Any = None
) -> Any:
  """Examples:

  get_value_by_path({'a': {'b': v}}, ['a', 'b'])
    -> v
  get_value_by_path({'a': {'b': [{'c': v1}, {'c': v2}]}}, ['a', 'b[]', 'c'])
    -> [v1, v2]
  """
  if keys == ['_self']:
    return data
  for i, key in enumerate(keys):
    if not data:
      return default_value
    if key.endswith('[]'):
      key_name = key[:-2]
      if key_name in data:
        return [
            get_value_by_path(d, keys[i + 1 :], default_value=default_value)
            for d in data[key_name]
        ]
      else:
        return default_value
    elif key.endswith('[0]'):
      key_name = key[:-3]
      if key_name in data and data[key_name]:
        return get_value_by_path(
            data[key_name][0], keys[i + 1 :], default_value=default_value
        )
      else:
        return default_value
    else:
      if key in data:
        data = data[key]
      elif isinstance(data, BaseModel) and hasattr(data, key):
        data = getattr(data, key)
      else:
        return default_value
  return data


class BaseModel(pydantic.BaseModel):
  """Base model with common configuration."""

  model_config = pydantic.ConfigDict(
      alias_generator=alias_generators.to_camel,
      populate_by_name=True,
      from_attributes=True,
      protected_namespaces=(),
      extra='forbid',
      arbitrary_types_allowed=True,
      ser_json_bytes='base64',
      val_json_bytes='base64',
      ignored_types=(typing.TypeVar,),
  )

  def __repr__(self) -> str:
    return super().__repr__()

  @classmethod
  def _from_response(
      cls: typing.Type['T'],
      *,
      response: dict[str, object],
      kwargs: dict[str, object],
  ) -> 'T':
    validated_response = cls.model_validate(response)
    return validated_response

  def to_json_dict(self) -> dict[str, object]:
    return self.model_dump(exclude_none=True, mode='json')


class CaseInSensitiveEnum(str, enum.Enum):
  """Case insensitive enum."""

  @classmethod
  def _missing_(cls, value: Any) -> Any:
    try:
      return cls[value.upper()]
    except KeyError:
      try:
        return cls[value.lower()]
      except KeyError:
        warnings.warn(f'{value} is not a valid {cls.__name__}')
        try:
          unknown_enum_val = super().__new__(cls, value)
          unknown_enum_val._name_ = str(value)
          unknown_enum_val._value_ = value
          return unknown_enum_val
        except:
          return None


T = typing.TypeVar('T', bound='BaseModel')