import io
import os
import jwt
import json
import base64
import datetime
from functools import wraps
from dotenv import load_dotenv

from flask_cors import CORS, cross_origin
from flask import Flask, jsonify, request
from flasgger import APISpec, Schema, Swagger, fields
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from pymongo.mongo_client import MongoClient

from PIL import Image
from model import Rim_Detector

load_dotenv()
# client = MongoClient(os.getenv("MONGO_URI"))
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
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["STATIC_DATE_FOR_AUTH"] = os.getenv("STATIC_DATE_FOR_AUTH")
app.config["AUTH_LOGIN"] = os.getenv("AUTH_LOGIN")
app.config["AUTH_PASSWORD"] = os.getenv("AUTH_PASSWORD")
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:8000", "https://carstomapp.github.io"]}})
model = Rim_Detector()

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
            if date == app.config["STATIC_DATE_FOR_AUTH"]:
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
        is_validated = data.get("login") == app.config["AUTH_LOGIN"] and data.get("password") == app.config["AUTH_PASSWORD"]
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


@app.route("/api/v1/nn", methods=['POST'])
@token_required
# @cross_origin()
def nn_endpoint():
    """
    Extracts the rim position from a frame
    ---
    description: Extracts the rim position from a frame
    responses:
        200:
            description: X and Y in image coordinates
            schema:
                $ref: "#/definitions/Pose2DSchema"
    """
    image_data = request.json.get("image")
    image_data = bytes(image_data[image_data.find(",") + 1:], encoding="ascii")
    image = Image.open(io.BytesIO(base64.b64decode(image_data))).convert('L')

    now = datetime.datetime.now()
    date_time = now.strftime("%m%d%Y_%H%M%S")
    image.save(f"logs/{date_time}.jpg")

    output = model(image)
    with open(f"logs/{date_time}.json", "w") as outfile:
        json.dump(output, outfile)


    if output is None:
        rim_coordinates = {
            "coordinates": []
        }
    else:
        rim_coordinates = {
            "coordinates": [output]
        }

    return jsonify(RimCoordinatesSchema().dump(rim_coordinates))


class CarBrandsSchema(Schema):
    brands = fields.List(fields.Str())

class CarModelsSchema(Schema):
    models = fields.List(fields.Str())

class CarModelYearsSchema(Schema):
    years = fields.List(fields.Str())

class Pose2DSchema(Schema):
    x = fields.Int()
    y = fields.Int()
    x_normal = fields.Float()
    y_normal = fields.Float()
    z_normal = fields.Float()

class RimCoordinatesSchema(Schema):
    coordinates = fields.Nested(Pose2DSchema, many=True)

template = spec.to_flasgger(
    app,
    definitions=[CarBrandsSchema, CarModelsSchema, CarModelYearsSchema, Pose2DSchema, RimCoordinatesSchema],
    paths=[get_brands, get_models, get_years, nn_endpoint]
)

swag = Swagger(
    app,
    template=template,
    # decorators=[token_required],
)


if __name__ == "__main__":
    app.run(debug=True)