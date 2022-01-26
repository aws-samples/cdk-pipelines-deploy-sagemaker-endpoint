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

# This is the file that implements a flask server to do inferences. It's the file that you will modify to
# implement the scoring for your own algorithm.

import flask
import os
import logging
import sys

# own libs
from scorer import ScoringService

# Logger
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# The flask app for serving predictions
app = flask.Flask(__name__)


@app.route("/ping", methods=["GET"])
def ping():
    ScoringService.load_model()
    status = 200 if ScoringService.model else 404
    logger.info("Model status for {}: {}.".format(os.getpid(), str(status)))
    return flask.Response(response="\n", status=200, mimetype="application/json")


@app.route("/invocations", methods=["POST"])
def transformation():
    if flask.request.content_type == "application/json":
        ScoringService.load_model()
        features = ScoringService.input_fn(flask.request)
        res = ScoringService.predict_fn(features)
    else:
        err_msg = f"Type [{flask.request.content_type}] not supported"
        logger.error(err_msg)
        raise ValueError(err_msg)

    logger.info("Finished processing request")
    return flask.jsonify(res.tolist()), 200
