python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. address.proto
python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. message.proto
python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. userfav.proto
