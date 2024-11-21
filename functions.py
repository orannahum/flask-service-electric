import pandas as pd
import numpy as np

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


