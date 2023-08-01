#!/bin/bash

protoc -I=./protos --python_out=model --experimental_allow_proto3_optional protos/*.proto