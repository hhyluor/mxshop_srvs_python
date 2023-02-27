python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. order.proto
python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. goods.proto
python -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. inventory.proto