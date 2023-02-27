# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: userfav.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\ruserfav.proto\x1a\x1bgoogle/protobuf/empty.proto\"1\n\x0eUserFavRequest\x12\x0e\n\x06userId\x18\x01 \x01(\x05\x12\x0f\n\x07goodsId\x18\x02 \x01(\x05\"2\n\x0fUserFavResponse\x12\x0e\n\x06userId\x18\x01 \x01(\x05\x12\x0f\n\x07goodsId\x18\x02 \x01(\x05\"D\n\x13UserFavListResponse\x12\r\n\x05total\x18\x01 \x01(\x05\x12\x1e\n\x04\x64\x61ta\x18\x02 \x03(\x0b\x32\x10.UserFavResponse2\xec\x01\n\x07UserFav\x12\x33\n\nGetFavList\x12\x0f.UserFavRequest\x1a\x14.UserFavListResponse\x12\x35\n\nAddUserFav\x12\x0f.UserFavRequest\x1a\x16.google.protobuf.Empty\x12\x38\n\rDeleteUserFav\x12\x0f.UserFavRequest\x1a\x16.google.protobuf.Empty\x12;\n\x10GetUserFavDetail\x12\x0f.UserFavRequest\x1a\x16.google.protobuf.EmptyB\tZ\x07.;protob\x06proto3')



_USERFAVREQUEST = DESCRIPTOR.message_types_by_name['UserFavRequest']
_USERFAVRESPONSE = DESCRIPTOR.message_types_by_name['UserFavResponse']
_USERFAVLISTRESPONSE = DESCRIPTOR.message_types_by_name['UserFavListResponse']
UserFavRequest = _reflection.GeneratedProtocolMessageType('UserFavRequest', (_message.Message,), {
  'DESCRIPTOR' : _USERFAVREQUEST,
  '__module__' : 'userfav_pb2'
  # @@protoc_insertion_point(class_scope:UserFavRequest)
  })
_sym_db.RegisterMessage(UserFavRequest)

UserFavResponse = _reflection.GeneratedProtocolMessageType('UserFavResponse', (_message.Message,), {
  'DESCRIPTOR' : _USERFAVRESPONSE,
  '__module__' : 'userfav_pb2'
  # @@protoc_insertion_point(class_scope:UserFavResponse)
  })
_sym_db.RegisterMessage(UserFavResponse)

UserFavListResponse = _reflection.GeneratedProtocolMessageType('UserFavListResponse', (_message.Message,), {
  'DESCRIPTOR' : _USERFAVLISTRESPONSE,
  '__module__' : 'userfav_pb2'
  # @@protoc_insertion_point(class_scope:UserFavListResponse)
  })
_sym_db.RegisterMessage(UserFavListResponse)

_USERFAV = DESCRIPTOR.services_by_name['UserFav']
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'Z\007.;proto'
  _USERFAVREQUEST._serialized_start=46
  _USERFAVREQUEST._serialized_end=95
  _USERFAVRESPONSE._serialized_start=97
  _USERFAVRESPONSE._serialized_end=147
  _USERFAVLISTRESPONSE._serialized_start=149
  _USERFAVLISTRESPONSE._serialized_end=217
  _USERFAV._serialized_start=220
  _USERFAV._serialized_end=456
# @@protoc_insertion_point(module_scope)
