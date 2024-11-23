from flask import Flask, request, render_template, jsonify
import pandas as pd
import numpy as np
import firebase_functions as functions

app = Flask(__name__, template_folder='templates', static_folder='public')


def read_df_all_and_df(uploaded_file_path=None, uploaded_file_df=None):
    if uploaded_file_path is not None:
        df_all = pd.read_csv(uploaded_file_path,
                         encoding='utf-8',
                         names=['Date', 'Start Time', 'Consumption (kWh)'],  # Manually set column names
                         usecols=[0, 1, 2],  # Only use the relevant columns
                         skip_blank_lines=True
                         )
    elif uploaded_file_df is not None:
        # Use the provided DataFrame directly
        df_all = uploaded_file_df
    else:
        # Neither a path nor a DataFrame was provided
        raise ValueError("Either 'uploaded_file_path' or 'uploaded_file_df' must be provided.")
    
    
    df = df_all.iloc[11:]
    df = df[df['Date'].str.strip().astype(bool) & df['Start Time'].str.strip().astype(bool)]

    # Combine Date and Start Time columns into a single datetime column
    df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Start Time'], format='%d/%m/%Y %H:%M', errors='coerce')

    # Drop rows with invalid datetime values (NaT)
    df = df.dropna(subset=['Datetime'])
    df['Consumption (kWh)'] = df['Consumption (kWh)'].astype(str).apply(
        lambda x: '0' + x if x.startswith('.') else x).astype(float)

    # Set Datetime as the index
    df.set_index('Datetime', inplace=True)

    # Create a new datetime range with 15-minute intervals, covering the full range of the data
    full_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq='15min')

    # Reindex the dataframe with the complete range, filling missing values with NaN
    df = df.reindex(full_range)

    # Fill NaN values with 0
    df.fillna(0, inplace=True)

    # Rename the index back to 'Datetime'
    df.index.name = 'Datetime'

    df = df[['Consumption (kWh)']]
    # df sort by index
    df = df.sort_index()
    return df_all, df



def apply_discount(df, plan):
    discount = plan['discount']
    discount_hours = plan['hours']
    discount_days = {day.lower() for day in plan['days']}  # Convert to set for faster lookup

    len_of_year = 2
    # Safely calculate discount rate for each row based on the years passed
    if isinstance(discount, list):
        # i want the first 365 days discount[0] and the second 365 days discount[1]
        # discounted dates is [[first year dates], [second year dates], ....[last year dates]]
        discounted_hours_list = []
        for i in range(len(discount)):
            if i != len(discount) - 1:
                relevant_hours = df.index[(df.index >= df.index.min() + pd.DateOffset(years=i)) & (df.index < df.index.min() + pd.DateOffset(years=i + 1))]
            else:
                relevant_hours = df.index[(df.index >= df.index.min() + pd.DateOffset(years=i))]
            relevant_hours = relevant_hours[(relevant_hours.hour.isin(discount_hours)) & (
                relevant_hours.strftime('%A').str.lower().isin(discount_days))]
            discounted_hours_list.append(relevant_hours)
        discount_rate = np.zeros(len(df))
        for i in range(len(discount)):
            discount_rate[np.isin(df.index, discounted_hours_list[i])] = discount[i]

    else:
        discount_rate = discount
    current_hours = df.index.hour
    current_days = df.index.strftime('%A').str.lower()

    # Create mask for hours and days that fall within the discount period
    discount_mask = np.isin(current_hours, discount_hours) & np.isin(current_days, list(discount_days))

    # Apply the discount where the mask is True, otherwise keep the original value
    return np.where(discount_mask, df['Consumption (kWh)'] * (1 - discount_rate), df['Consumption (kWh)'])



price_of_kWh = 0.6145
plans = {
  "plan_hevrat_hashmal1": {
    "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
    "discount": 0,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "work_with_meter": ["Smart Meter", "Simple Meter"]
  },
  "plan_cellcom1": {
    "hours": [14, 15, 16, 17, 18, 19],
    "discount": 0.18,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
     "work_with_meter": ["Smart Meter"]
  },
  "plan_cellcom2": {
    "hours": [7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    "discount": 0.15,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
    "work_with_meter": ["Smart Meter"]
  },
  "plan_cellcom3": {
    "hours": [23, 0, 1, 2, 3, 4, 5, 6],
    "discount": 0.2,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "work_with_meter": ["Smart Meter"]
  },
  "plan_cellcom4": {
    "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
    "discount": [0.05, 0.06, 0.07],
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "work_with_meter": ["Smart Meter", "Simple Meter"]
  },
  "plan_paz1": {
    "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
    "discount": 0.07,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "work_with_meter": ["Smart Meter", "Simple Meter"]
  },
  "plan_electra_power1": {
    "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
    "discount": [0.05, 0.06, 0.07],
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "work_with_meter": ["Smart Meter", "Simple Meter"]
  },
  "plan_electra_power2": {
    "hours": [23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    "discount": [0.08, 0.09, 0.1],
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "work_with_meter": ["Smart Meter"]

  },
  "plan_electra_power3": {
    "hours": [23, 0, 1, 2, 3, 4, 5, 6],
    "discount": 0.2,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "work_with_meter": ["Smart Meter"]
  },
    "plan_hot1": {
    "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
    "discount": [0.05, 0.06, 0.07],
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      "work_with_meter": ["Smart Meter", "Simple Meter"]
  },
    "plan_hot2": {
    "hours": [7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    "discount": 0.15,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
      "work_with_meter": ["Smart Meter"]
  },
  "plan_hot3": {
    "hours": [23, 0, 1, 2, 3, 4, 5, 6],
    "discount": 0.2,
    "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    "work_with_meter": ["Smart Meter"]
  },
    "plan_hot4": {
        "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
        "discount": 0.07,
        "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      "work_with_meter": ["Smart Meter", "Simple Meter"],
      "more_services_that_needed": ["hot_triple"]
    },
    "plan_hot5": {
        "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
        "discount": 0.1,
        "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "work_with_meter": ["Smart Meter", "Simple Meter"],
      "more_services_that_needed": ["hot_triple", "hot_mobile"]
    },
    "plan_hot6": {
        "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
        "discount": 0.06,
        "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "work_with_meter": ["Smart Meter", "Simple Meter"],
      "more_services_that_needed": ["next_double"]
    }
}

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
        ## price of price_of_kWh
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
    app.run(debug=True)
