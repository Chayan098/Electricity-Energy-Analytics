
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from datetime import date, timedelta

# -------------------------------------------------
# PAGE CONFIGURATION
# -------------------------------------------------

st.set_page_config(
    page_title="Energy Analytics Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Electricity & Renewable Energy Dashboard")

st.caption(
    "Analyze electricity generation and renewable energy "
    "contributions using real-world data."
)

# -------------------------------------------------
# API CONFIGURATION
# -------------------------------------------------

API_URL = "https://api.energy-charts.info/v2/public_power"

COUNTRIES = {
    "Germany": "de",
    "France": "fr",
    "Spain": "es",
    "Italy": "it",
    "Netherlands": "nl",
    "Switzerland": "ch",
    "Poland": "pl",
    "Sweden": "se",
    "Denmark": "dk",
    "Austria": "at",
    "Finland": "fi",
    "Norway": "no",
    "United Kingdom": "uk",
    "European Union": "eu"
}


# -------------------------------------------------
# FETCH ELECTRICITY DATA
# -------------------------------------------------

@st.cache_data(ttl=900)
def fetch_energy_data(country_code, start_date, end_date):

    params = {
        "country": country_code,
        "start": start_date,
        "end": end_date
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    payload = response.json()

    records = []

    for row in payload.get("data", []):

        record = {
            "timestamp": row.get("timestamp")
        }

        values = row.get("values", {})

        if isinstance(values, dict):
            record.update(values)

        records.append(record)

    if not records:
        return pd.DataFrame(), {}

    df = pd.DataFrame(records)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce"
    )

    df = df.dropna(subset=["timestamp"])

    # Convert electricity values to numeric

    for column in df.columns:

        if column != "timestamp":

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    df = df.sort_values("timestamp")

    # Read series names from API metadata

    series_info = {}

    for item in payload.get("series", []):

        if isinstance(item, dict):

            series_id = item.get("id")

            if series_id:
                series_info[series_id] = item.get(
                    "name",
                    series_id.replace("_", " ").title()
                )

    return df, series_info


# -------------------------------------------------
# RENEWABLE ENERGY CLASSIFICATION
# -------------------------------------------------

def is_renewable(source_name):

    name = source_name.lower()

    renewable_keywords = [
        "solar",
        "wind",
        "hydro",
        "water",
        "biomass",
        "geothermal",
        "renewable",
        "run of river",
        "pumped storage"
    ]

    return any(
        keyword in name
        for keyword in renewable_keywords
    )


def display_name(source, series_info):

    return series_info.get(
        source,
        source.replace("_", " ").title()
    )


# -------------------------------------------------
# SIDEBAR
# -------------------------------------------------

st.sidebar.header("Dashboard Settings")

selected_country = st.sidebar.selectbox(
    "Select Country",
    list(COUNTRIES.keys()),
    index=0
)

period = st.sidebar.selectbox(
    "Select Time Period",
    ["Last 1 Day", "Last 3 Days", "Last 7 Days"],
    index=2
)

days = {
    "Last 1 Day": 1,
    "Last 3 Days": 3,
    "Last 7 Days": 7
}[period]

end_date = date.today()
start_date = end_date - timedelta(days=days - 1)

st.sidebar.caption(
    f"Date range: {start_date} to {end_date}"
)

if st.sidebar.button("Refresh Energy Data"):

    st.cache_data.clear()
    st.rerun()


# -------------------------------------------------
# MAIN DASHBOARD
# -------------------------------------------------

try:

    country_code = COUNTRIES[selected_country]

    df, series_info = fetch_energy_data(
        country_code,
        start_date.isoformat(),
        end_date.isoformat()
    )

    if df.empty:

        st.warning(
            "No electricity generation data is available "
            "for this country and period."
        )

    else:

        # -----------------------------------------
        # IDENTIFY GENERATION SOURCES
        # -----------------------------------------

        source_columns = [
            column
            for column in df.columns
            if column != "timestamp"
        ]

        if not source_columns:

            st.warning("No generation sources were returned.")

        else:

            # Latest available observation

            latest_row = df.iloc[-1]

            latest_values = latest_row[
                source_columns
            ].dropna()

            # -------------------------------------
            # TOTAL GENERATION
            # -------------------------------------

            total_generation = latest_values.sum()

            renewable_sources = [
                source
                for source in source_columns
                if is_renewable(
                    display_name(source, series_info)
                )
            ]

            renewable_generation = latest_values[
                renewable_sources
            ].sum() if renewable_sources else 0

            renewable_percentage = (
                renewable_generation / total_generation * 100
                if total_generation > 0
                else 0
            )

            non_renewable_generation = (
                total_generation - renewable_generation
            )

            # -------------------------------------
            # KEY METRICS
            # -------------------------------------

            st.subheader(
                f"Electricity Overview — {selected_country}"
            )

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Latest Total Generation",
                f"{total_generation:,.0f} MW"
            )

            col2.metric(
                "Renewable Generation",
                f"{renewable_generation:,.0f} MW"
            )

            col3.metric(
                "Renewable Share",
                f"{renewable_percentage:.1f}%"
            )

            col4.metric(
                "Number of Sources",
                len(latest_values)
            )

            st.caption(
                "Metrics represent the latest available time interval "
                "in the selected period, not the entire period's total."
            )

            st.divider()

            # -------------------------------------
            # PREPARE DATA FOR CHARTS
            # -------------------------------------

            chart_df = df.copy()

            chart_df = chart_df.rename(
                columns={
                    source: display_name(source, series_info)
                    for source in source_columns
                }
            )

            chart_sources = [
                display_name(source, series_info)
                for source in source_columns
            ]

            # -------------------------------------
            # ELECTRICITY GENERATION TREND
            # -------------------------------------

            st.subheader("Electricity Generation Trend")

            trend_chart = px.line(
                chart_df,
                x="timestamp",
                y=chart_sources,
                title="Electricity Generation by Energy Source",
                labels={
                    "timestamp": "Time",
                    "value": "Generation (MW)",
                    "variable": "Energy Source"
                }
            )

            trend_chart.update_layout(
                hovermode="x unified"
            )

            st.plotly_chart(
                trend_chart,
                use_container_width=True
            )

            st.divider()

            # -------------------------------------
            # ENERGY MIX
            # -------------------------------------

            st.subheader("Latest Electricity Energy Mix")

            mix_df = pd.DataFrame({
                "Energy Source": [
                    display_name(source, series_info)
                    for source in latest_values.index
                ],
                "Generation (MW)": latest_values.values
            })

            mix_df = mix_df.dropna()

            mix_df = mix_df[
                mix_df["Generation (MW)"] > 0
            ]

            if not mix_df.empty:

                mix_chart = px.pie(
                    mix_df,
                    names="Energy Source",
                    values="Generation (MW)",
                    hole=0.45,
                    title="Electricity Generation Share"
                )

                st.plotly_chart(
                    mix_chart,
                    use_container_width=True
                )

            st.divider()

            # -------------------------------------
            # RENEWABLE VS NON-RENEWABLE
            # -------------------------------------

            st.subheader(
                "Renewable vs Non-Renewable Generation"
            )

            energy_type_df = pd.DataFrame({
                "Energy Type": [
                    "Renewable",
                    "Non-Renewable"
                ],
                "Generation (MW)": [
                    renewable_generation,
                    non_renewable_generation
                ]
            })

            energy_type_chart = px.bar(
                energy_type_df,
                x="Energy Type",
                y="Generation (MW)",
                color="Energy Type",
                text_auto=".2s",
                title="Electricity Generation Comparison"
            )

            st.plotly_chart(
                energy_type_chart,
                use_container_width=True
            )

            st.divider()

            # -------------------------------------
            # SOLAR AND WIND ANALYSIS
            # -------------------------------------

            st.subheader("Solar and Wind Generation")

            solar_wind_sources = [
                source
                for source in chart_sources
                if "solar" in source.lower()
                or "wind" in source.lower()
            ]

            if solar_wind_sources:

                solar_wind_chart = px.area(
                    chart_df,
                    x="timestamp",
                    y=solar_wind_sources,
                    title="Solar and Wind Electricity Generation",
                    labels={
                        "timestamp": "Time",
                        "value": "Generation (MW)",
                        "variable": "Energy Source"
                    }
                )

                st.plotly_chart(
                    solar_wind_chart,
                    use_container_width=True
                )

            else:

                st.info(
                    "Solar or wind generation data is not available "
                    "for this selection."
                )

            st.divider()

            # -------------------------------------
            # TOP GENERATION SOURCES
            # -------------------------------------

            st.subheader("Top Electricity Generation Sources")

            top_sources = mix_df.sort_values(
                "Generation (MW)",
                ascending=False
            )

            top_chart = px.bar(
                top_sources,
                x="Generation (MW)",
                y="Energy Source",
                orientation="h",
                title="Latest Generation by Source"
            )

            top_chart.update_layout(
                yaxis={"categoryorder": "total ascending"}
            )

            st.plotly_chart(
                top_chart,
                use_container_width=True
            )

            st.divider()

            # -------------------------------------
            # DATA TABLE
            # -------------------------------------

            st.subheader("Latest Generation Records")

            display_df = chart_df.copy()

            display_df = display_df.sort_values(
                "timestamp",
                ascending=False
            )

            st.dataframe(
                display_df.head(20),
                use_container_width=True,
                hide_index=True
            )

            # -------------------------------------
            # DOWNLOAD CSV
            # -------------------------------------

            st.subheader("Download Electricity Dataset")

            csv_data = df.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                label="Download Energy Data CSV",
                data=csv_data,
                file_name="electricity_generation.csv",
                mime="text/csv"
            )

            st.caption(
                "Source: Energy-Charts.info, Fraunhofer ISE. "
                "Data is subject to availability and reporting delays."
            )

except requests.exceptions.HTTPError as error:

    st.error(
        f"The energy API returned an error: {error}. "
        "Please wait before refreshing."
    )

except requests.exceptions.RequestException as error:

    st.error(
        f"Unable to connect to the energy API: {error}"
    )

except (KeyError, ValueError, TypeError) as error:

    st.error(
        f"Unable to process the energy data: {error}"
    )
