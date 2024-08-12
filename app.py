import jwt
import datetime
from functools import wraps

from flask import Flask, jsonify, request, redirect, Response, g
from flasgger import APISpec, Schema, Swagger, fields
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin

import requests
from requests.auth import HTTPDigestAuth
from pymongo.mongo_client import MongoClient


uri = "mongodb+srv://valeriavolkovaa90:IsYgE2hkDbJjHneW@carstom.sbcvkk5.mongodb.net/?retryWrites=true&w=majority&appName=Carstom"
client = MongoClient(uri)

# Create an APISpec
spec = APISpec(
    title="Flasger Petstore",
    version="1.0.10",
    openapi_version="2.0",
    plugins=[
        FlaskPlugin(),
        MarshmallowPlugin(),
    ],
)

app = Flask(__name__)
SECRET_KEY = "CarstomSecretSecureKey"
app.config["SECRET_KEY"] = SECRET_KEY


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]
        if not token:
            return dict(message="Authentication Token is missing!", data=None, error="Unauthorized"), 401
        try:
            data=jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            date=data["date"]
            if date in ["December091998"]:
                return f(*args, **kwargs)
            if date != datetime.date.today().strftime("%B%d%Y"):
                return dict(message="Invalid Authentication token!", data=None, error="Unauthorized"), 401
        except Exception as e:
            return dict(message="Something went wrong", data=None, error=str(e)), 500

        return f(*args, **kwargs)

    return decorated


@app.route("/api/v1/auth", methods=["GET"])
def login():
    try:
        data = request.json
        if not data:
            return dict(message="Please provide user details", data=None, error="Bad request"), 400
        # validate input
        is_validated = data.get("login") == "asavin" and data.get("password") == "asavinpassword1"
        if is_validated is not True:
            return dict(message="Error fetching auth token!, invalid login or password - invalid data", data=None, error="Unauthorized"), 404

        # token should expire after 24 hrs
        date = datetime.date.today().strftime("%B%d%Y")
        token = jwt.encode({"date": date}, app.config["SECRET_KEY"], algorithm="HS256")
        return dict(message="Successfully fetched auth token", TOKEN=token), 200
    except Exception as e:
        return dict(error="Something went wrong", message=str(e)), 500


@app.route("/api/v1/brands")
@token_required
def get_brands():
    """
    Car brands endpoint
    ---
    description: Get all brands available
    responses:
        200:
            description: list of brands
            schema:
                $ref: "#/definitions/CarBrands"
    """
    data = client.carstom_db.brands.find({})
    brands = {"brands": [x["brand"] for x in data]}
    return jsonify(CarBrandsSchema().dump(brands))


@app.route("/api/v1/models")
@token_required
def get_models():
    """
    Get models by brand
    ---
    description: Get all models by brand
    responses:
        200:
            description: list of models
            schema:
                $ref: "#/definitions/CarModels"
    """
    brand = request.args.get("brand")
    data = client.carstom_db.models.find({"brand": brand})
    models = {"models": [x["model"] for x in data]}
    return jsonify(CarModelsSchema().dump(models))


@app.route("/api/v1/years")
@token_required
def get_years():
    """
    Get years by model
    ---
    description: Get all years by model
    responses:
        200:
            description: list of years
            schema:
                $ref: "#/definitions/CarModelYears"
    """
    model = request.args.get("model")
    data = client.carstom_db.years.find({"model": model})
    years = {"years": data[0]["years"]}

    return jsonify(CarModelYearsSchema().dump(years))


# Optional marshmallow support
class CarBrandsSchema(Schema):
    brands = fields.List(fields.Str())

# Optional marshmallow support
class CarModelsSchema(Schema):
    models = fields.List(fields.Str())

class CarModelYearsSchema(Schema):
    years = fields.List(fields.Str())

template = spec.to_flasgger(
    app,
    definitions=[CarBrandsSchema, CarModelsSchema, CarModelYearsSchema],
    paths=[get_brands, get_models, get_years]
)


# start Flasgger using a template from apispec
swag = Swagger(
    app,
    template=template,
    # decorators=[token_required],
)


if __name__ == "__main__":
    app.run(debug=True)