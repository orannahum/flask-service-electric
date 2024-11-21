from flask import Flask, request, render_template, jsonify
import pandas as pd
from functions import apply_discount, read_df_all_and_df
import json
from config import price_of_kWh

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Load plans configuration
with open('/Users/guybasson/udemy_projects/pythonProject/electric_project_moshe_shine/plans.json', encoding='utf-8') as f:
    plans = json.load(f)

top_n = 5
client_plan_en = "plan_electra_power1"

# Route for rendering the upload form
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Route for processing uploaded CSV
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Read uploaded file into DataFrame
    try:
        file_df = pd.read_csv(
            file,
            encoding='utf-8',  # Ensure the CSV is read with UTF-8
            names=['Date', 'Start Time', 'Consumption (kWh)'],  # Manually set column names
            usecols=[0, 1, 2],  # Only use relevant columns
            skip_blank_lines=True
        )
        df_all, uploaded_file_df = read_df_all_and_df(uploaded_file_df=file_df)
        df_info = df_all.iloc[:10]
        client = df_info.iloc[3, 0]
        address = df_info.iloc[3, 1]
        meter_code = int(df_info.iloc[7, 0])
        meter_number = int(df_info.iloc[7, 1])
        client_info = {"client": client, "address": address, "meter_code": meter_code, "meter_number": meter_number}
    except Exception as e:
        return jsonify({"error": f"Error reading file: {e}"}), 400

    # Process the data and get results
    try:
        results_dict = {}
        ## prie of price_of_kWh
        results_dict["price_of_kWh"] = price_of_kWh
        ## add client info to results
        results_dict["client_info"] = client_info
        ## add client plan
        results_dict["client_plan_en"] = client_plan_en
        ## add plans
        results_dict["relevant_plans"] = plans
        # Hourly aggregation
        uploaded_file_df = uploaded_file_df.iloc[-100:]
        df_hourly = uploaded_file_df.resample('h').sum()
        df_hourly_agg = df_hourly.groupby(df_hourly.index.hour).mean()
        results_dict['hourly_agg'] = df_hourly_agg.to_dict(orient='index')
        # Apply plans and calculate cumulative sums
        for plan in plans:
            uploaded_file_df[plan] = apply_discount(uploaded_file_df, plans[plan]) * price_of_kWh
        uploaded_file_df_cumsum = uploaded_file_df.cumsum()
        uploaded_file_df_cumsum.index = uploaded_file_df_cumsum.index.strftime('%Y-%m-%d %H:%M:%S')
        results_dict['price_sumcum'] = uploaded_file_df_cumsum.to_dict(orient='index')
        ## add diff between client plan and other plans
        df_diff_saving = pd.DataFrame()
        for plan in plans:
            if plan != client_plan_en:
                df_diff_saving[plan + '_diff'] = uploaded_file_df_cumsum[client_plan_en] - uploaded_file_df_cumsum[plan]

        results_dict['diff_saving'] = df_diff_saving.to_dict()
        ## show sorted plans by price from history data
        final_series_plans = uploaded_file_df_cumsum.iloc[-1].sort_values(ascending=True)
        # name is Price(ILS) and the index is the name of the plan

        final_series_plans.index.name = 'plan'
        final_series_plans.name = 'price(ILS)'
        final_df_plans = final_series_plans.reset_index()
        results_dict['final_df_plans'] = final_df_plans.to_dict(orient='index')
    except Exception as e:
        return jsonify({"error": f"Error processing file: {e}"}), 500

    # Return results rendered in the template
    return render_template('index.html', results=results_dict)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002, debug=True)
