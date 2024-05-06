import os

from flasgger import Swagger
from flask import Flask, jsonify, render_template, request

from main import run_simulation

app = Flask(__name__)
swagger = Swagger(app)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/simulate", methods=["GET"])
def simulate():
    """
    This is the API documentation for the simulate endpoint as /apidocs/
    ---
    parameters:
      - name: battery_capacity
        in: query
        type: number
        required: false
        default: 1.0
        description: The capacity of the battery.
      - name: charge_efficiency
        in: query
        type: number
        required: false
        default: 0.9
        description: The charge efficiency of the battery.
      - name: discharge_efficiency
        in: query
        type: number
        required: false
        default: 0.9
        description: The discharge efficiency of the battery.
      - name: start_date
        in: query
        type: string
        required: false
        default: '2015-02-01'
        description: The start date of the simulation in the format 'YYYY-MM-DD'.
      - name: end_date
        in: query
        type: string
        required: false
        default: '2015-02-02'
        description: The end date of the simulation in the format 'YYYY-MM-DD'.
      - name: price_model
        in: query
        type: string
        required: false
        default: 'SimulatedPriceModel'
        description: The price model to use for the simulation.
      - name: csv_path
        in: query
        type: string
        required: false
        default: 'data/time_series/time_series_60min_singleindex_filtered.csv'
        description: The path to the CSV file with the time series data.
      - name: log_level
        in: query
        type: string
        required: false
        default: 'INFO'
        description: The log level.
    responses:
      200:
        description: The result of the simulation.
    """
    args = [
        "--battery_capacity",
        str(request.args.get("battery_capacity", default=1.0, type=float)),
        "--charge_efficiency",
        str(request.args.get("charge_efficiency", default=0.9, type=float)),
        "--discharge_efficiency",
        str(request.args.get("discharge_efficiency", default=0.9, type=float)),
        "--start_date",
        request.args.get("start_date", default="2015-02-01", type=str),
        "--end_date",
        request.args.get("end_date", default="2015-02-02", type=str),
        "--price_model",
        request.args.get("price_model", default="SimulatedPriceModel", type=str),
        "--csv_path",
        request.args.get(
            "csv_path",
            default=os.path.join(
                "data", "time_series", "time_series_60min_singleindex_filtered.csv"
            ),
            type=str,
        ),
        "--log_level",
        request.args.get("log_level", default="INFO", type=str),
    ]

    result = run_simulation(args)
    if result is None:
        return jsonify({"error": "An error occurred during the simulation."}), 500
    else:
        return jsonify(
            [
                {"current_date": r[0], "schedule_df": r[1].to_dict(), "daily_pnl": r[2]}
                for r in result
            ]
        )


if __name__ == "__main__":
    app.run(debug=True)
