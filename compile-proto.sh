#!/bin/bash

protoc -I=./resources/protos --python_out=model/protos --experimental_allow_proto3_optional resources/protos/*.proto