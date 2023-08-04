#!/bin/bash

protoc --python_out=./ --experimental_allow_proto3_optional model/protos/*.proto