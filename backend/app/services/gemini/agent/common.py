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

logger = logging.getLogger('google_genai.common')

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
  """
  if not data:
    data = {}
  if not keys:
    return
  
  key = keys[0]
  if key.endswith('[]'):
    key = key[:-2]
    if len(keys) == 1:
      data[key] = value
    else:
      if key not in data:
        data[key] = []
      for item in value:
        item_dict = {}
        set_value_by_path(item_dict, keys[1:], item)
        data[key].append(item_dict)
  else:
    if len(keys) == 1:
      data[key] = value
    else:
      if key not in data:
        data[key] = {}
      set_value_by_path(data[key], keys[1:], value)


def get_value_by_path(data: Optional[dict[Any, Any]], keys: list[str]) -> Any:
  """Examples:

  get_value_by_path({'a': {'b': v}}, ['a', 'b'])
    -> v
  get_value_by_path({'a': {'b': [{'c': v1}, {'c': v2}]}}, ['a', 'b[]', 'c'])
    -> [v1, v2]
  """
  if not data:
    return None
  if not keys:
    return data
  
  key = keys[0]
  if key.endswith('[]'):
    key = key[:-2]
    if key not in data:
      return []
    result = []
    for item in data[key]:
      value = get_value_by_path(item, keys[1:])
      if value is not None:
        result.append(value)
    return result
  else:
    if key not in data:
      return None
    if len(keys) == 1:
      return data[key]
    return get_value_by_path(data[key], keys[1:])


class BaseModel(pydantic.BaseModel):
    """Base model class for SDK types."""
    
    class Config:
        extra = "allow"
        populate_by_name = True


class CaseInSensitiveEnum(str, enum.Enum):
    """Case-insensitive enum."""
    
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None
