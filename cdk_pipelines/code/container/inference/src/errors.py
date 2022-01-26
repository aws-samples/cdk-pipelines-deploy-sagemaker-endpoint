# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


def template(message, payload, status_code=500):
    return {"message": message, "payload": payload, "status_code": status_code}


class ScoringFailure(Exception):
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv

    @classmethod
    def model_not_loaded(cls, payload=None):
        return cls(**template("Model could not be loaded", payload))

    @classmethod
    def model_wrong_format(cls, payload=None):
        return cls(**template("Supplied model is in wrong format", payload))

    @classmethod
    def missing_env(cls, payload=None):
        return cls(**template("Endpoint environment is not configured properly", payload))

    @classmethod
    def unsupported_payload(cls, payload=None):
        return cls(**template("Model supports JSON inputs only ", payload, 415))

    @classmethod
    def empty_data(cls, payload=None):
        return cls(**template("Received empty data file", payload, 400))

    @classmethod
    def data_not_supported(cls, payload=None):
        return cls(**template("Model does not support supplied data schema", payload, 400))

    @classmethod
    def cannot_read_data(cls, payload=None):
        return cls(**template("Could not read input data", payload))

    @classmethod
    def could_not_return_data(cls, payload=None):
        return cls(**template("Could not return data to invoke lambda", payload, 416))

    @classmethod
    def request_not_supported(cls, payload=None):
        return cls(**template("No handler for JSON content", payload, 400))
